//! Lightweight regex-free entity extractor.
//!
//! Phase 1: recognize commands, libraries, error codes, file paths,
//! and code-symbol-like identifiers from memory content.
//! No LLM, no regex crate -- purely deterministic, microseconds per call.

mod lexicon;

use crate::entity::{EntityRef, EntityType};
use std::collections::HashSet;

use lexicon::{FILE_EXTS, KNOWN_COMMANDS, KNOWN_CONCEPTS, KNOWN_LIBRARIES};

pub fn extract(text: &str) -> Vec<EntityRef> {
    let mut found: Vec<EntityRef> = Vec::new();
    let mut seen: HashSet<(EntityType, String)> = HashSet::new();
    let lower = text.to_lowercase();

    for lib in KNOWN_LIBRARIES {
        if contains_word(&lower, lib) {
            push_unique(&mut found, &mut seen, EntityType::Library, lib);
        }
    }
    for cmd in KNOWN_COMMANDS {
        if lower.contains(cmd) {
            push_unique(&mut found, &mut seen, EntityType::Command, cmd);
        }
    }
    for c in KNOWN_CONCEPTS {
        if contains_word(&lower, c) {
            push_unique(&mut found, &mut seen, EntityType::Concept, c);
        }
    }
    extract_errors(text, &mut found, &mut seen);
    extract_files(text, &mut found, &mut seen);
    extract_symbols(text, &mut found, &mut seen);
    found
}

fn push_unique(
    out: &mut Vec<EntityRef>,
    seen: &mut HashSet<(EntityType, String)>,
    kind: EntityType,
    name: &str,
) {
    let normalized = name.trim().to_lowercase();
    if normalized.is_empty() {
        return;
    }
    let key = (kind, normalized);
    if seen.insert(key) {
        out.push(EntityRef::new(kind, name.trim().to_string()));
    }
}

fn contains_word(haystack: &str, needle: &str) -> bool {
    let bytes = haystack.as_bytes();
    let n = needle.len();
    if n == 0 || n > haystack.len() {
        return false;
    }
    let mut start = 0;
    while let Some(pos) = haystack[start..].find(needle) {
        let abs = start + pos;
        let before_ok = abs == 0 || !is_word_byte(bytes[abs - 1]);
        let after_idx = abs + n;
        let after_ok = after_idx >= haystack.len() || !is_word_byte(bytes[after_idx]);
        if before_ok && after_ok {
            return true;
        }
        start = abs + n;
        if start >= haystack.len() {
            break;
        }
    }
    false
}

fn is_word_byte(b: u8) -> bool {
    b.is_ascii_alphanumeric() || b == b'_'
}

fn extract_errors(text: &str, out: &mut Vec<EntityRef>, seen: &mut HashSet<(EntityType, String)>) {
    for tok in tokens(text) {
        if tok.len() == 3 && tok.chars().all(|c| c.is_ascii_digit()) {
            if let Ok(n) = tok.parse::<u16>() {
                if (400..600).contains(&n) {
                    push_unique(out, seen, EntityType::Error, &format!("HTTP_{n}"));
                }
            }
            continue;
        }
        if tok.len() >= 4
            && tok
                .chars()
                .all(|c| c.is_ascii_uppercase() || c == '_' || c.is_ascii_digit())
            && tok.chars().any(|c| c.is_ascii_alphabetic())
            && (tok.contains('_') || tok.len() >= 6)
        {
            push_unique(out, seen, EntityType::Error, &tok);
        }
    }
}

fn extract_files(text: &str, out: &mut Vec<EntityRef>, seen: &mut HashSet<(EntityType, String)>) {
    for tok in tokens(text) {
        let lower = tok.to_lowercase();
        let looks_like_path = lower.contains('/') || lower.contains('\\');
        let has_ext = FILE_EXTS.iter().any(|e| lower.ends_with(e));
        if looks_like_path || has_ext {
            let cleaned: String = tok
                .trim_end_matches(['.', ',', ';', ':', ')', ']'])
                .to_string();
            if cleaned.len() >= 3 {
                push_unique(out, seen, EntityType::File, &cleaned);
            }
        }
    }
}

fn extract_symbols(text: &str, out: &mut Vec<EntityRef>, seen: &mut HashSet<(EntityType, String)>) {
    for tok in tokens(text) {
        let raw = tok.trim_end_matches('(');
        if raw.len() < 3 {
            continue;
        }
        if raw.contains('/') || raw.contains('\\') || raw.contains('.') {
            continue;
        }
        if raw.chars().all(|c| c.is_ascii_digit()) {
            continue;
        }
        if !raw.chars().all(|c| c.is_ascii_alphanumeric() || c == '_') {
            continue;
        }
        let has_lower = raw.chars().any(|c| c.is_ascii_lowercase());
        let has_upper = raw.chars().any(|c| c.is_ascii_uppercase());
        let has_underscore = raw.contains('_');
        let is_camel_or_pascal = has_lower && has_upper;
        let is_snake_multi = has_underscore && raw.len() >= 5;
        let is_called = tok.ends_with('(');
        if is_camel_or_pascal || is_snake_multi || is_called {
            let lc = raw.to_lowercase();
            if KNOWN_LIBRARIES.iter().any(|l| *l == lc) {
                continue;
            }
            if KNOWN_CONCEPTS.iter().any(|l| *l == lc) {
                continue;
            }
            push_unique(out, seen, EntityType::Symbol, raw);
        }
    }
}

fn tokens(s: &str) -> Vec<String> {
    let mut out = Vec::new();
    let mut cur = String::new();
    for c in s.chars() {
        if c.is_alphanumeric() || matches!(c, '_' | '-' | '.' | '/' | '\\' | '(') {
            cur.push(c);
        } else if !cur.is_empty() {
            out.push(std::mem::take(&mut cur));
        }
    }
    if !cur.is_empty() {
        out.push(cur);
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn names_of(refs: &[EntityRef], kind: EntityType) -> Vec<String> {
        refs.iter()
            .filter(|r| r.kind == kind)
            .map(|r| r.name.to_lowercase())
            .collect()
    }

    #[test]
    fn extracts_libraries_and_commands() {
        let refs = extract("pnpm install hangs on Windows behind corporate proxy");
        let libs = names_of(&refs, EntityType::Library);
        assert!(libs.contains(&"pnpm".to_string()));
        let cmds = names_of(&refs, EntityType::Command);
        assert!(cmds.contains(&"pnpm install".to_string()));
    }

    #[test]
    fn extracts_http_error() {
        let refs = extract("API returned 401 after refresh token rotation");
        let errs = names_of(&refs, EntityType::Error);
        assert!(errs.contains(&"http_401".to_string()));
    }

    #[test]
    fn extracts_path_and_symbol() {
        let refs = extract("UserModel in src/models/user.ts breaks when calling login()");
        let files = names_of(&refs, EntityType::File);
        let syms = names_of(&refs, EntityType::Symbol);
        assert!(files.iter().any(|f| f.contains("user.ts")));
        assert!(syms.iter().any(|s| s == "usermodel" || s == "login"));
    }

    #[test]
    fn ignores_short_lowercase_words() {
        let refs = extract("the cat sat on the mat");
        assert!(refs.iter().all(|r| !matches!(r.kind, EntityType::Symbol)));
    }
}
