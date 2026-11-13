# Clay Formulas Library

Reusable JS formula expressions for Clay formula columns. Copy-paste, swap field references, deploy.

**Clay formula constraints (from build learnings):**
- No IIFE: Clay silently ignores `(function(){...})()` and `(()=>{...})()`
- No multi-statement arrow function bodies (`(w) => { const x = ...; return x; }`)
- No `for` loops, `let`, or `const` declarations
- No `try/catch`
- ✅ Chained method calls (`.replace()`, `.split()`, `.filter()`, `.map()`, `.join()`, etc.)
- ✅ Single-expression arrow bodies (`(w) => w.toUpperCase()`)
- ✅ Ternary chains (`a ? b : c ? d : e`)
- ✅ Regex literals
- ✅ `.indexOf()`, `.includes()`, `.charAt()`, `.slice()`, `.test()`, `.match()`

---

## clean_full_name

**Purpose:** Normalize a messy "Full Name" string into a clean `First Last` (or `First X.` for single-initial surnames), preserving compound LATAM surnames and stripping credentials, parentheticals, CJK characters, and standalone numbers.

**Use case:** Cleaning LATAM hire names (or any person name) for cold email copy where you reference the person by name.

**Input:** `{{f_full_name}}`: the raw full name field

**Output:** Clean `First Last` string. Empty input → empty output.

**Formula:**

```javascript
!{{f_full_name}} ? "" :
  String({{f_full_name}})
    .replace(/\s*\([^)]*\)\s*/g, " ")
    .replace(/[一-鿿]+/g, " ")
    .replace(/[,;:'"\[\]]/g, " ")
    .replace(/\b(MBA|PhD|Ph\.D|PMP|KMP|CPA|CFA|MSC|BA|BS|MD|JD|SAFe|Certified|Senior|Junior|Jr|Sr|II|III|IV)\b\.?/gi, " ")
    .replace(/\b\d+\b/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b(de la|de las|de los|del|de|da|do|dos|das|van der|van|von|di)\s+(\S+)\s*$/i, "§$1 $2")
    .split(" ")
    .filter(w => w.length >= 1)
    .map(w => w.charAt(0) === "§" ? w.slice(1).toLowerCase() : (w.replace(/\.$/, "").length === 1 ? w.charAt(0).toUpperCase() + "." : w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()))
    .filter((w, i, arr) => i === 0 || i === arr.length - 1 || (i === arr.length - 2 && ["de","da","del","do","dos","das","van","von","di","la","las","los"].indexOf(w.toLowerCase()) !== -1))
    .join(" ")
    .trim()
```

**How it works:**
1. Strip parentheticals: `Caio Bastos (凯奥)` → `Caio Bastos`
2. Strip CJK characters: handles unicode side-cases
3. Strip stray punctuation: `.,;:'"[]`
4. Strip credentials: `MBA, PhD, PMP, KMP, CPA, CFA, MSC, BA, BS, MD, JD, SAFe, Certified, Senior, Junior, Jr, Sr, II, III, IV`
5. Strip standalone numbers
6. Compound-surname sentinel: insert `§` before connectors (`de la`, `de`, `da`, `do`, `dos`, `das`, `del`, `van der`, `van`, `von`, `di`) when they appear right before the last token
7. Split + tokenize with title-casing; single-letter tokens become `X.`
8. Final filter: keep first token + last token + connector if it sits between them

**Verified test cases:**

| Input | Output |
|---|---|
| `Rafael Moreira` | `Rafael Moreira` |
| `Tomas R.` | `Tomas R.` |
| `Arjun K` | `Arjun K.` |
| `Caio Bastos (凯奥)` | `Caio Bastos` |
| `Rodrigo Vasconcelos de Souza` | `Rodrigo de Souza` |
| `José Carlos de Melo` | `José de Melo` |
| `Héctor Ramírez Ochoa` | `Héctor Ochoa` |
| `Daniela Gómez Arriaga` | `Daniela Arriaga` |
| `Ana Clara Ribeiro` | `Ana Ribeiro` |
| `Beatriz Nogueira, MBA` | `Beatriz Nogueira` |
| `Pedro M L.` | `Pedro L.` |
| `Bruno T.` | `Bruno T.` |
| `Luis Miguel Castro` | `Luis Castro` |

**Known limitations:**
- Compound surnames where credentials follow (e.g., `Marcos Prado, KMP, Certified SAFe 6 A`) may degrade to `Marcos A.` because the trailing letter survives all strips. Manually patch these rows if rare.
- Compound connector list is finite. If a name uses an unlisted connector (e.g., `du`, `den`), it'll be dropped along with everything between first + last token.

**Deployed in:**
- A client's WF1 Accounts table → `Clean LATAM Hire Name` column
