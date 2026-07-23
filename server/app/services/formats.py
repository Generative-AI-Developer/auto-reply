"""Render request numbers into each operator's submission syntax.

Pure functions - no DB, no ORM, no docx - so every emitter can be exercised
directly from a REPL or a test. `build_blocks` is the only entry point the
export route needs; it turns grouped rows into ready-to-print Blocks.

Two fields drive the routing and both are unvalidated free text in the DB, so
`norm_network` / `norm_type` are deliberately forgiving (case, spacing, the
common `Gatway` misspelling, `Jazz` for Mobilink).

Operators disagree on almost everything - date order, separator, whether many
numbers share one line, and whether an IMEI keeps its 15th digit - so each
(network, type) pair gets its own emitter rather than a parameterised template.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

# --- Vocabulary ---------------------------------------------------------------
TELENOR = "telenor"
UFONE = "ufone"
MOBILINK = "mobilink"
ZONG = "zong"

CDR = "cdr"
IMEI = "imei"
GATEWAY = "gateway"

#: A CDR set carries at most this many numbers; the rest spill into further sets.
CDR_SET_SIZE = 10

#: Telenor will not serve a single request spanning more than this; longer
#: durations are split into two non-overlapping sets.
TELENOR_SPLIT_DAYS = 180

_NETWORK_ALIASES = {
    "telenor": TELENOR,
    "ufone": UFONE,
    "mobilink": MOBILINK,
    "jazz": MOBILINK,
    "zong": ZONG,
}

#: The four networks shown under the CDRs / IMEIs sections, in document order.
#: A network-less IMEI request fans out across all of these.
SECTION_NETWORKS = (TELENOR, MOBILINK, UFONE, ZONG)


def norm_network(raw: str | None) -> str:
    """'  TELENOR ' -> 'telenor'. Unknown/blank -> ''."""
    key = (raw or "").strip().lower()
    return _NETWORK_ALIASES.get(key, "")


def norm_type(raw: str | None) -> str:
    """'Gatway' -> 'gateway'. Unknown/blank -> ''."""
    key = (raw or "").strip().lower()
    if key.startswith("gat"):  # gateway, and the common 'Gatway' misspelling
        return GATEWAY
    if key == "cdr":
        return CDR
    if key == "imei":
        return IMEI
    return ""


# --- Dates --------------------------------------------------------------------
def _dmy_slash(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _dmy_dash(d: date) -> str:
    return d.strftime("%d-%m-%Y")


def _mdy_slash(d: date) -> str:
    return d.strftime("%m/%d/%Y")


def date_ranges(network: str, rtype: str, days: int | None,
                today: date | None = None) -> list[tuple[date, date]]:
    """Date ranges to request, most recent first.

    End is today, start is `days` back. Telenor caps a single request at 180
    days, so a longer duration becomes two adjacent, non-overlapping ranges:
    the recent 180 and everything before it. The split only applies to the
    formats Telenor actually serves (CDR / IMEI); an unformatted list is not
    duplicated across two windows.
    """
    end = today or date.today()
    span = days or 0

    if network == TELENOR and rtype in (CDR, IMEI) and span > TELENOR_SPLIT_DAYS:
        # Telenor serves at most 180 days per request. Split into the recent 180
        # and the 180 before it. A request longer than 360 days is capped at
        # those two windows - never a third set, never a set wider than 180 -
        # so Days = 500 still yields the same two 180-day sets as Days = 360.
        split = end - timedelta(days=TELENOR_SPLIT_DAYS)  # start of set 1
        set1 = (split, end)
        second_span = min(span, 2 * TELENOR_SPLIT_DAYS)
        set2 = (end - timedelta(days=second_span), split - timedelta(days=1))
        return [set1, set2]
    return [(end - timedelta(days=span), end)]


def expand_identifier_specs(
    request_type: str,
    network: str,
    duration_days: int | None,
    today: date | None = None,
) -> list[tuple[str, int, date | None, date | None, int | None]]:
    """Fan one entered number out into the records it should become.

    Returns one `(network, part, date_from, date_to, days)` spec per record:

    - A network-less IMEI becomes one record per operator (Telenor, Mobilink,
      Ufone, Zong), so each operator's reply is requested and tracked on its
      own. `part` is 0, no window, days unchanged.
    - A Telenor CDR longer than 180 days becomes two records, one per date
      window (recent 180 + the prior 180), each carrying that window so it is
      exported and matched independently. `part` is 1 then 2, and `days` is the
      window's own length (180 per set - the remainder is capped at 180), so a
      set reads as its 180-day request rather than the full span.
    - Everything else stays a single record with the network and days as given.

    Only the IMEI fan-out coins canonical operator names (the network was
    blank); every other case preserves the caller's original `network` string
    so unknown/less-common networks aren't normalised away.
    """
    rtype = norm_type(request_type)
    net = norm_network(network)

    if rtype == IMEI and not net:
        return [(op.title(), 0, None, None, duration_days) for op in SECTION_NETWORKS]

    if rtype == CDR and net == TELENOR and (duration_days or 0) > TELENOR_SPLIT_DAYS:
        windows = date_ranges(TELENOR, CDR, duration_days, today)
        span = duration_days or 0
        specs: list[tuple[str, int, date | None, date | None, int | None]] = []
        for i, (start, end) in enumerate(windows):
            # Set 1 is the full 180-day cap; set 2 is whatever remains of the
            # span, itself capped at another 180.
            wdays = TELENOR_SPLIT_DAYS if i == 0 else min(span - TELENOR_SPLIT_DAYS, TELENOR_SPLIT_DAYS)
            specs.append((network, i + 1, start, end, wdays))
        return specs

    return [(network, 0, None, None, duration_days)]


# --- Number shaping -----------------------------------------------------------
def normalize_msisdn(value: str) -> str:
    """Stored numbers are digits-only; operators want them 92-prefixed."""
    v = "".join(ch for ch in value if ch.isdigit())
    if v.startswith("92"):
        return v
    if v.startswith("0"):
        return "92" + v[1:]
    if len(v) == 10:  # bare '3001234567'
        return "92" + v
    return v


def imei_for(network: str, value: str) -> str:
    """Shape an IMEI for a network.

    A valid IMEI is 15 digits ending in a 0 check digit. Telenor and Mobilink
    want the 14-digit body; Ufone and Zong want the full 15. We rebuild the
    15-digit form as body + "0", so a value whose 15th digit isn't 0 (or that
    arrived 14-digit) is corrected to end in 0.
    """
    body = "".join(ch for ch in value if ch.isdigit())[:14]
    if network in (TELENOR, MOBILINK):
        return body
    return body + "0"


def looks_like_imei(value: str) -> bool:
    """A 14/15-digit value is an IMEI, not a phone number.

    MSISDNs top out at 12 digits (92 + 10) and CNICs at 13, so 14+ digits is
    unambiguously an IMEI even when it turns up inside a request labelled CDR.
    """
    return len("".join(ch for ch in value if ch.isdigit())) >= 14


def _chunk(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)] or [[]]


def _dedup(items) -> list[str]:
    """De-duplicate preserving first-seen order."""
    return list(dict.fromkeys(items))


# --- Blocks -------------------------------------------------------------------
@dataclass
class Block:
    """One printable unit: a heading plus its formatted lines.

    `network` is the normalised operator ('' for Gateway / unknown); the doc
    builder uses it to colour each network's heading distinctly.
    """

    heading: str
    subtitle: str = ""
    lines: list[str] = field(default_factory=list)
    note: str = ""
    network: str = ""


def _label(network: str, rtype: str) -> str:
    parts = [p for p in (network.title(), rtype.upper()) if p]
    return " · ".join(parts) or "Unspecified"


def render_group(network: str, rtype: str, days: int | None, numbers: list[str],
                 today: date | None = None,
                 window: tuple[date, date] | None = None) -> list[Block]:
    """Emit every set for one (network, type, days) group.

    Sets come from two independent causes: the Telenor 180+180 *date-range*
    split (two windows, so two sets even for a single number), and the CDR
    10-per-set *number* cap. A group of 10 or fewer numbers on a network that
    doesn't date-split is therefore always a single, unlabelled set.

    `window` pins the group to one explicit date range (a persisted Telenor
    split window) instead of recomputing the split from `days` - so a stored
    part-2 record renders its own prior-180 window rather than being re-split.
    """
    ranges = [window] if window is not None else date_ranges(network, rtype, days, today)
    # Only CDR is capped into sets of 10; IMEI and Gateway go out whole.
    chunks_per_range = CDR_SET_SIZE if rtype == CDR else len(numbers) or 1
    total = len(ranges) * len(_chunk(numbers, chunks_per_range))

    blocks: list[Block] = []
    n = 0
    for start, end in ranges:
        for chunk in _chunk(numbers, chunks_per_range):
            n += 1
            # Gateway ignores network; unformatted "other" types aren't bound to
            # a network either, so their heading is the type alone (e.g. "IPDR").
            if rtype == GATEWAY:
                heading = "Gateway"
            elif rtype in (CDR, IMEI):
                heading = _label(network, rtype)
            else:
                heading = rtype.upper()
            # No duration (e.g. an NIC row) -> no fabricated date range.
            if days is None:
                subtitle = ""
            else:
                subtitle = f"{days} days · {_dmy_slash(start)} to {_dmy_slash(end)}"
                if total > 1:
                    subtitle += f"  ·  Set {n} of {total}"
            block = _emit(network, rtype, start, end, chunk, heading, subtitle)
            block.network = network
            blocks.append(block)
    return blocks


def _emit(network: str, rtype: str, start: date, end: date, numbers: list[str],
          heading: str, subtitle: str) -> Block:
    b = Block(heading=heading, subtitle=subtitle)

    if rtype == GATEWAY:
        # Gateway is routed by request type alone - network is irrelevant here.
        for raw in numbers:
            b.lines.append(f"R;{raw};{_dmy_slash(start)};{_dmy_slash(end)};")
            b.lines.append(f"B;{raw};{_dmy_slash(start)};{_dmy_slash(end)};")
        return b

    if rtype == CDR:
        # De-dup after shaping: two raw numbers can normalise to the same MSISDN.
        shaped = _dedup(normalize_msisdn(v) for v in numbers)
        if network == TELENOR:
            b.lines.append(f"tpn:{','.join(shaped)}:{_dmy_dash(start)}:{_dmy_dash(end)}:")
        elif network == UFONE:
            b.lines.append(f"MSISDN|Both|{_mdy_slash(start)}|{_mdy_slash(end)}|{':'.join(shaped)}")
        elif network == MOBILINK:
            for m in shaped:  # Mobilink takes a list, one entry per line
                b.lines.append(f"A;{m};{_dmy_slash(start)};{_dmy_slash(end)};")
        else:  # Zong / unknown network: no format, list the shaped numbers
            b.lines.extend(shaped)
        return b

    if rtype == IMEI:
        # De-dup after shaping: Telenor/Mobilink keep 14 digits, so IMEIs that
        # differ only in the 15th digit collapse to one entry (not repeated).
        shaped = _dedup(imei_for(network, v) for v in numbers)
        if network == TELENOR:
            b.lines.append(f"tpi:{','.join(shaped)}:{_dmy_dash(start)}:{_dmy_dash(end)}:")
        elif network == UFONE:
            b.lines.append(f"MEI|Call|{_mdy_slash(start)}|{_mdy_slash(end)}|{':'.join(shaped)}")
        elif network == MOBILINK:
            for m in shaped:
                b.lines.append(f"I;{m};{_dmy_slash(start)};{_dmy_slash(end)};")
        else:  # Zong / unknown network
            b.lines.extend(shaped)
        return b

    # Any other request type (not CDR / IMEI / Gateway): no format is defined,
    # so just list the numbers as-is, the same way Zong is handled.
    b.lines.extend(numbers)
    return b


def build_document(rows: list[tuple],
                   today: date | None = None) -> dict[str, list[Block]]:
    """Group `(network, request_type, days, number[, window])` rows into sections.

    Days is part of the grouping key on purpose: Telenor and Ufone join many
    numbers into a single line under one date range, so numbers with different
    durations can never share a set. An optional 5th element pins the row to an
    explicit date `window` (a persisted Telenor split), which also joins the
    grouping key so the two windows render as two distinct sets.
    """
    groups: dict[tuple[str, str, int | None, tuple[date, date] | None], list[str]] = {}
    for row in rows:
        raw_network, raw_type, days, value, *rest = row
        window = rest[0] if rest else None
        network = norm_network(raw_network)
        rtype = norm_type(raw_type)
        # An IMEI-shaped value in a CDR request is really an IMEI - route it to
        # the IMEI grouping for its network instead of mixing it into the CDR
        # set (where its long digit-string would corrupt the operator format).
        if rtype == CDR and looks_like_imei(value):
            rtype = IMEI
        if not rtype:
            # Not CDR / IMEI / Gateway: there is no format, so keep the original
            # request-type label and let the numbers list under their own name.
            rtype = (raw_type or "").strip() or "Unspecified"

        if rtype == IMEI and not network and window is None:
            # IMEI request with no network specified: emit every network's IMEI
            # output so the value is ready for whichever operator it's sent to -
            # formatted for Telenor/Mobilink/Ufone, listed (15-digit) for Zong.
            # (Records created via the per-operator fan-out already carry a
            # network, so they skip this render-time fan-out.)
            for net in SECTION_NETWORKS:
                groups.setdefault((net, rtype, days, None), []).append(value)
        else:
            groups.setdefault((network, rtype, days, window), []).append(value)

    sections: dict[str, list[Block]] = {"CDR": [], "IMEI": [], "GATEWAY": [], "MANUAL": []}
    for (network, rtype, days, window), numbers in groups.items():
        deduped = list(dict.fromkeys(numbers))  # preserve first-seen order
        blocks = render_group(network, rtype, days, deduped, today, window=window)

        if rtype == GATEWAY:
            sections["GATEWAY"].extend(blocks)
        elif rtype in (CDR, IMEI):
            # Routed by type, not network: every CDR/IMEI number belongs under
            # its section - formatted when the network is known, listed under a
            # "network not set" subheading otherwise - so none get lost in Other.
            sections[rtype.upper()].extend(blocks)
        else:
            # Only genuinely non-CDR/IMEI/Gateway types (NIC, FT, ...) land here.
            sections["MANUAL"].extend(blocks)
    return sections
