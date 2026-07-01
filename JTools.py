import re
import math
from decimal import Decimal, InvalidOperation
from urllib.parse import unquote, urlsplit, urlunsplit, parse_qsl, quote

import keypirinha as kp
import keypirinha_util as kpu


class JTools(kp.Plugin):
    """
    Keypirinha plugin exposing keywords:
      - jsum: sum numbers from free-form text using several locale/spacing interpretations
      - jurl: decode URLs/text, remove tracking params, unwrap redirect URLs recursively
      - jstring: text transformations like "Read-me" to: Readme, README, readme, read-me, ReadMe, readMe, READ-ME, read_me, READ_ME
      - jnumber: extract numbers from free-form text using several locale/spacing interpretations. e.g. "The total of 12 items is 1,234.56 USD" => 12, 1234.56
      - jjj: all-in-one keyword that combines jsum, jurl, jstring, and jnumber results

    Execute any result item to copy its output to clipboard.
    """

    ITEMCAT_RESULT = kp.ItemCategory.USER_BASE + 1

    TRACKING_PARAMS = {
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "utm_id", "utm_name", "utm_cid", "utm_reader", "utm_referrer",
        "utm_social", "utm_social-type", "fbclid", "gclid", "dclid", "gbraid",
        "wbraid", "msclkid", "mc_cid", "mc_eid", "mkt_tok", "vero_id",
        "wickedid", "yclid", "igshid", "si", "spm", "ref_src", "ref_url",
        "s_cid", "cmpid", "camp", "campaign_id", "adgroupid", "adid",
        "sr_share", "feature", "source", "ncid", "ef_id", "_hsenc", "_hsmi"
    }

    REDIRECT_PARAM_NAMES = (
        "url", "u", "target", "dest", "destination", "redirect", "redirect_url",
        "redir", "r", "to", "next", "continue", "continue_url", "return",
        "return_to", "return_url", "out", "goto", "view", "q"
    )
    HYPHEN_NUMBER_RE = re.compile(r"\d+-\d+")
    NUMERIC_CHUNK_RE = re.compile(r"[\d][\d\s,\.]*")
    EN_NUMBER_RE = re.compile(r"(?<!\d)(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?!\d)")
    EU_NUMBER_RE = re.compile(r"(?<!\d)(?:\d{1,3}(?:[ .]\d{3})+|\d+)(?:,\d+)?(?!\d)")
    SPACE_GROUPED_RE = re.compile(r"(?<!\d)(?:\d{1,3}(?: \d{3})+)(?:[\.,]\d+)?(?!\d)")
    GENERIC_DECIMAL_RE = re.compile(r"(?<!\d)\d+(?:[\.,]\d+)?(?!\d)")

    def on_start(self):
        pass

    def on_catalog(self):
        self.set_catalog([
            self.create_item(
                category=kp.ItemCategory.KEYWORD,
                label="jsum",
                short_desc="Sum numbers in free-form text using multiple interpretations",
                target="jsum",
                args_hint=kp.ItemArgsHint.REQUIRED,
                hit_hint=kp.ItemHitHint.NOARGS,
            ),
            self.create_item(
                category=kp.ItemCategory.KEYWORD,
                label="jurl",
                short_desc="Decode, clean tracking params, and unwrap redirect URLs",
                target="jurl",
                args_hint=kp.ItemArgsHint.REQUIRED,
                hit_hint=kp.ItemHitHint.NOARGS,
            ),
            self.create_item(
                category=kp.ItemCategory.KEYWORD,
                label="jstring",
                short_desc="Transform text into various casing and formatting styles",
                target="jstring",
                args_hint=kp.ItemArgsHint.REQUIRED,
                hit_hint=kp.ItemHitHint.NOARGS,
            ),
            self.create_item(
                category=kp.ItemCategory.KEYWORD,
                label="jnumber",
                short_desc="Extract numbers from free-form text using multiple interpretations",
                target="jnumber",
                args_hint=kp.ItemArgsHint.REQUIRED,
                hit_hint=kp.ItemHitHint.NOARGS,
            ),
            self.create_item(
                category=kp.ItemCategory.KEYWORD,
                label="jjj",
                short_desc="All-in-one: sum, URL, string, and number tools combined",
                target="jjj",
                args_hint=kp.ItemArgsHint.REQUIRED,
                hit_hint=kp.ItemHitHint.NOARGS,
            )
        ])

    def on_suggest(self, user_input, items_chain):
        if not items_chain:
            return

        keyword = items_chain[0].target()
        text = (user_input or "").strip()
        if not text:
            self.set_suggestions([], kp.Match.ANY, kp.Sort.NONE)
            return

        suggestions = []
        if keyword == "jsum":
            for item in self._suggest_jsum(text):
                suggestions.append(item)
        elif keyword == "jurl":
            for item in self._suggest_jurl(text):
                suggestions.append(item)
        elif keyword == "jstring":
            for item in self._suggest_jstring(text):
                suggestions.append(item)
        elif keyword == "jnumber":
            for item in self._suggest_jnumber(text):
                suggestions.append(item)
        elif keyword == "jjj":
            seen_targets = set()
            for func in (self._suggest_jsum, self._suggest_jurl, self._suggest_jstring, self._suggest_jnumber):
                for item in func(text):
                    t = item.target()
                    if t not in seen_targets:
                        seen_targets.add(t)
                        suggestions.append(item)

        self.set_suggestions(suggestions, kp.Match.ANY, kp.Sort.NONE)

    def on_execute(self, item, action):
        if item.category() != self.ITEMCAT_RESULT:
            return
        value = item.target() or ""
        if value:
            kpu.set_clipboard(value)

    # --------------------------
    # jsum
    # --------------------------
    def _suggest_jsum(self, text):
        results = []
        seen = set()

        modes = [
            ("en", "EN: comma thousands, dot decimal", self._sum_en),
            ("eu", "EU: space/dot thousands, comma decimal", self._sum_eu),
            ("space-grouped", "Space-grouped: '1 000' => 1000", self._sum_space_grouped),
            ("space-split", "Space-split: '1 000' => 1 + 000", self._sum_space_split),
        ]

        for mode_key, desc, func in modes:
            values = func(text)
            if not values:
                continue
            total = sum(values, Decimal("0"))
            rendered_total = self._format_decimal(total)
            rendered_values = " + ".join(self._format_decimal(v) for v in values[:12])
            if len(values) > 12:
                rendered_values += " + ..."

            payload = f"{rendered_total}"
            dedupe_key = (mode_key, payload)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            results.append(self.create_item(
                category=self.ITEMCAT_RESULT,
                label=rendered_total,
                short_desc=f"{desc} | {rendered_values} | Enter copies result",
                target=payload,
                args_hint=kp.ItemArgsHint.FORBIDDEN,
                hit_hint=kp.ItemHitHint.IGNORE,
            ))

        return results

    def _sum_en(self, text):
        values = []
        for raw in self.NUMERIC_CHUNK_RE.findall(text):
            for token in self.EN_NUMBER_RE.findall(raw.replace("\u00A0", " ")):
                value = self._decimal_from_generic(token)
                if value is not None:
                    values.append(value)
        return values
    
    def _sum_eu(self, text):
        values = []
        cleaned = text.replace("\u00A0", " ")
        for token in self.EU_NUMBER_RE.findall(cleaned):
            value = self._decimal_from_generic(token)
            if value is not None:
                values.append(value)
        return values

    def _sum_space_grouped(self, text):
        values = []
        cleaned = text.replace("\u00A0", " ")
        consumed = []

        for m in self.SPACE_GROUPED_RE.finditer(cleaned):
            token = m.group(0)
            value = self._decimal_from_generic(token)
            if value is not None:
                values.append(value)
                consumed.append((m.start(), m.end()))

        masked = list(cleaned)
        for start, end in consumed:
            for i in range(start, end):
                masked[i] = " "
        remaining = "".join(masked)

        for token in self.GENERIC_DECIMAL_RE.findall(remaining):
            value = self._decimal_from_generic(token)
            if value is not None:
                values.append(value)
        return values

    def _sum_space_split(self, text):
        values = []
        # Handle hyphenated numbers first
        consumed = []
        for m in self.HYPHEN_NUMBER_RE.finditer(text):
            token = m.group(0)
            value = self._decimal_from_generic(token)
            if value is not None:
                values.append(value)
                consumed.append((m.start(), m.end()))

        masked = list(text)
        for start, end in consumed:
            for i in range(start, end):
                masked[i] = " "
        remaining = "".join(masked)

        sanitized = re.sub(r"[^\d\.,]+", " ", remaining)
        for token in self.GENERIC_DECIMAL_RE.findall(sanitized):
            value = self._decimal_from_generic(token)
            if value is not None:
                values.append(value)
        return values

    def _decimal_from_generic(self, token):
        token = token.strip().replace(" ", "")
        if not token:
            return None

        token = token.replace("-", "") # For cases like 1234-567

        if token.count(",") and token.count("."):
            if token.rfind(',') > token.rfind('.'): # EU style: 1.234,56
                token = token.replace(".", "").replace(",", ".")
            else: # EN style: 1,234.56
                token = token.replace(",", "")
        elif token.count(',') > 0: # Only commas present
            if token.rfind(',') < len(token) - 3: # Treat as thousands: 1,234,567
                token = token.replace(",", "")
            else: # Treat as decimal: 123,45
                token = token.replace(",", ".")
        elif token.count('.') > 1: # Only dots present, treat as thousands: 1.234.567
            token = token.replace(".", "")

        try:
            return Decimal(token)
        except InvalidOperation:
            return None

    def _format_decimal(self, value):
        s = format(value.normalize(), "f") if value != value.to_integral() else format(value.quantize(Decimal("1")), "f")
        if "." in s:
            s = s.rstrip("0").rstrip(".")
        return s or "0"

    # --------------------------
    # jurl
    # --------------------------
    def _suggest_jurl(self, text):
        results = []
        seen = set()

        decoded = self._decode_until_stable(text)
        if decoded != text:
            self._append_result(results, seen, decoded, "Decoded", "Decoded percent-encoding")

        candidate = decoded if self._looks_like_url(decoded) else text
        if self._looks_like_url(candidate):
            cleaned = self._clean_url(candidate)
            unwrapped = self._unwrap_url(candidate)
            cleaned_unwrapped = self._clean_url(unwrapped) if self._looks_like_url(unwrapped) else unwrapped

            if cleaned != candidate:
                self._append_result(results, seen, cleaned, "Tracking removed", "Removed known tracking parameters")
            if unwrapped != candidate:
                self._append_result(results, seen, unwrapped, "Redirect unwrapped", "Extracted nested target URL")
            if cleaned_unwrapped != candidate and cleaned_unwrapped != cleaned and cleaned_unwrapped != unwrapped:
                self._append_result(results, seen, cleaned_unwrapped, "Unwrapped + cleaned", "Extracted nested URL and removed tracking params")

        else:
            maybe_url = self._find_first_url(decoded)
            if maybe_url:
                cleaned = self._clean_url(maybe_url)
                unwrapped = self._unwrap_url(maybe_url)
                if cleaned != maybe_url:
                    self._append_result(results, seen, cleaned, "Tracking removed", "Removed known tracking parameters from embedded URL")
                if unwrapped != maybe_url:
                    self._append_result(results, seen, unwrapped, "Redirect unwrapped", "Extracted nested target URL from embedded URL")

        return results

    def _append_result(self, results, seen, value, label_prefix, desc):
        value = (value or "").strip()
        if not value or value in seen:
            return
        seen.add(value)
        results.append(self.create_item(
            category=self.ITEMCAT_RESULT,
            label=value,
            short_desc=f"{label_prefix} | {desc} | Enter copies result",
            target=value,
            args_hint=kp.ItemArgsHint.FORBIDDEN,
            hit_hint=kp.ItemHitHint.IGNORE,
        ))

    def _decode_until_stable(self, text, limit=5):
        prev = text
        for _ in range(limit):
            cur = unquote(prev)
            if cur == prev:
                break
            prev = cur
        return prev

    def _looks_like_url(self, text):
        if not text:
            return False
        parsed = urlsplit(text)
        if parsed.scheme in ("http", "https") and parsed.netloc:
            return True
        if text.startswith("www."):
            return True
        return False

    def _normalize_url_for_parse(self, text):
        text = text.strip()
        if text.startswith("www."):
            return "https://" + text
        return text

    def _clean_url(self, text):
        text = self._normalize_url_for_parse(text)
        parsed = urlsplit(text)
        if not parsed.scheme or not parsed.netloc:
            return text

        kept = []
        for key, value in parse_qsl(parsed.query, keep_blank_values=True):
            kl = key.lower()
            if kl in self.TRACKING_PARAMS or kl.startswith("utm_"):
                continue
            kept.append((key, value))

        query = "&".join(
            f"{quote(k, safe='')}={quote(v, safe='')}" if v != "" else f"{quote(k, safe='')}="
            for k, v in kept
        ) if kept else ""

        cleaned = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))
        return cleaned

    def _unwrap_url(self, text, limit=5):
        current = self._normalize_url_for_parse(text)
        for _ in range(limit):
            parsed = urlsplit(current)
            if not parsed.scheme or not parsed.netloc:
                break

            found = None
            for key, value in parse_qsl(parsed.query, keep_blank_values=True):
                kl = key.lower()
                if kl in self.REDIRECT_PARAM_NAMES:
                    decoded = self._decode_until_stable(value)
                    if self._looks_like_url(decoded):
                        found = decoded
                        break
                    embedded = self._find_first_url(decoded)
                    if embedded:
                        found = embedded
                        break

            if not found:
                break
            if found == current:
                break
            current = found
        return current

    def _find_first_url(self, text):
        m = re.search(r"https?://[^\s<>\]\)\}\"']+", text)
        return m.group(0) if m else None

    # --------------------------
    # jstring
    # --------------------------
    def _get_words(self, text):
        # Split by space, underscore, or hyphen
        words = re.split(r'[\s_-]+', text)
        # Split by case changes (camelCase)
        cased_words = []
        for word in words:
            if not word: continue
            # Split on uppercase letters, but don't split acronyms
            parts = re.split('(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])', word)
            cased_words.extend(p for p in parts if p)
        return [w.lower() for w in cased_words if w]

    def _suggest_jstring(self, text):
        results = []
        seen = set()
        words = self._get_words(text)
        if not words:
            return []

        transformations = {
            "Title Case": "".join(w.capitalize() for w in words),
            "UPPER CASE": "".join(w.upper() for w in words),
            "lower case": "".join(words),
            "Sentence case": words[0].capitalize() + "".join(words[1:]),
            "CamelCase": "".join(w.capitalize() for w in words),
            "lowerCamelCase": words[0] + "".join(w.capitalize() for w in words[1:]),
            "kebab-case": "-".join(words),
            "UPPER-KEBAB-CASE": "-".join(w.upper() for w in words),
            "snake_case": "_".join(words),
            "UPPER_SNAKE_CASE": "_".join(w.upper() for w in words),
            "Title_Snake_Case": "_".join(w.capitalize() for w in words),
            "Space Separated": " ".join(words),
            "Title Space Separated": " ".join(w.capitalize() for w in words),
        }

        for desc, transformed in transformations.items():
            if transformed in seen:
                continue
            seen.add(transformed)
            results.append(self.create_item(
                category=self.ITEMCAT_RESULT,
                label=transformed,
                short_desc=f"{desc} | Enter copies result",
                target=transformed,
                args_hint=kp.ItemArgsHint.FORBIDDEN,
                hit_hint=kp.ItemHitHint.IGNORE,
            ))

        return results

    # --------------------------
    # jnumber
    # -------------------------- 
    def _suggest_jnumber(self, text):
        results = []
        seen = set()

        # Extract numbers using the same methods as jsum
        numbers = set()
        numbers.update(self._sum_en(text))
        numbers.update(self._sum_eu(text))
        numbers.update(self._sum_space_grouped(text))
        numbers.update(self._sum_space_split(text))

        for number in sorted(numbers, reverse=True):
            formatted = self._format_decimal(number)
            if formatted not in seen:
                seen.add(formatted)
                results.append(self.create_item(
                    category=self.ITEMCAT_RESULT,
                    label=formatted,
                    short_desc=f"Extracted number | Enter copies result",
                    target=formatted,
                    args_hint=kp.ItemArgsHint.FORBIDDEN,
                    hit_hint=kp.ItemHitHint.IGNORE,
                ))
        

        return results
    
