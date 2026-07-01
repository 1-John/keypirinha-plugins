# JTools – Keypiranha Plugin

A powerful all-in-one Keypiranha plugin for text processing, number extraction, URL manipulation, and string transformations.

## Features

### **jsum** – Sum Numbers in Free-Form Text
Extract and sum numbers from unstructured text with multiple locale and spacing interpretations.

- **EN Mode**: Comma as thousands separator, dot as decimal (e.g., `1,234.56`)
- **EU Mode**: Space/dot as thousands separator, comma as decimal (e.g., `1.234,56`)
- **Space-Grouped Mode**: Treats spaces as thousands separators (e.g., `1 000 000`)
- **Space-Split Mode**: Treats spaces as separators between distinct numbers (e.g., `1 000` → 1 + 000)

**Example:** `"The costs are 1,234.50 and 2,345.75 USD"` → `3,580.25`

---

### **jurl** – Decode, Clean & Unwrap URLs
Process URLs with three main capabilities:

- **Decode**: Recursively URL-decode percent-encoded text
- **Remove Tracking**: Strip known tracking parameters (UTM, Facebook, Google, etc.)
- **Unwrap Redirects**: Extract target URLs from redirect parameters

Supports recursive unwrapping to follow redirect chains.

**Example:** `"https://example.com?utm_source=email&url=https%3A%2F%2Ftarget.com"` → `"https://target.com"`

---

### **jstring** – Text Transformations
Convert text between multiple casing and formatting styles:

- `Title Case`
- `UPPER CASE`
- `lower case`
- `Sentence case`
- `CamelCase`
- `lowerCamelCase`
- `kebab-case`
- `UPPER-KEBAB-CASE`
- `snake_case`
- `UPPER_SNAKE_CASE`
- `Title_Snake_Case`
- `Space Separated`
- `Title Space Separated`

**Example:** `"Read-me"` → `Readme`, `README`, `readme`, `read-me`, `ReadMe`, `readMe`, `READ-ME`, `read_me`, `READ_ME`

---

### **jnumber** – Extract Numbers
Pull all numbers from text using multiple locale interpretations (same extraction methods as `jsum`).

Returns individual numbers sorted in descending order.

**Example:** `"The total of 12 items is 1,234.56 USD"` → `1234.56`, `12`

---

### **jjj** – All-in-One
Combines results from `jsum`, `jurl`, `jstring`, and `jnumber` in a single search, deduplicating results.

---

## Installation

1. Clone this repository into your Keypiranha plugins directory:
   ```bash
   git clone https://github.com/1-John/keypiranha-plugins ~/.config/Keypiranha/InstalledPackages/jtools
