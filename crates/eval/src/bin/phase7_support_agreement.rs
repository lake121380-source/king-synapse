use anyhow::{bail, Context, Result};
use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};
use synapse_eval::phase7_support_agreement::{analyze_support_agreement, SupportAgreementPaths};

fn parse_args() -> Result<(SupportAgreementPaths, PathBuf, PathBuf, bool)> {
    let mut values = BTreeMap::new();
    let mut verify = false;
    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        if arg == "--verify" {
            verify = true;
            continue;
        }
        if !arg.starts_with("--") {
            bail!("unexpected_argument:{arg}");
        }
        let value = args
            .next()
            .with_context(|| format!("missing_value_for:{arg}"))?;
        values.insert(arg, PathBuf::from(value));
    }
    let take = |key: &str| -> Result<PathBuf> {
        values
            .get(key)
            .cloned()
            .with_context(|| format!("missing_required_argument:{key}"))
    };
    Ok((
        SupportAgreementPaths {
            protocol: take("--protocol")?,
            reviewer_a: take("--reviewer-a")?,
            reviewer_b: take("--reviewer-b")?,
            support_packet: take("--support-packet")?,
            boundary_gold: take("--boundary-gold")?,
            execution_outcome: take("--execution-outcome")?,
            analyzer_source: take("--analyzer-source")?,
            binary_source: take("--binary-source")?,
        },
        take("--report")?,
        take("--worklist")?,
        verify,
    ))
}

fn serialized(value: &serde_json::Value) -> Result<Vec<u8>> {
    Ok((serde_json::to_string_pretty(value)? + "\n").into_bytes())
}

fn write_or_verify(path: &Path, bytes: &[u8], verify: bool) -> Result<()> {
    if verify {
        let existing = fs::read(path).with_context(|| format!("read {}", path.display()))?;
        if existing != bytes {
            bail!("deterministic_replay_mismatch:{}", path.display());
        }
        return Ok(());
    }
    if path.exists() {
        let existing = fs::read(path).with_context(|| format!("read {}", path.display()))?;
        if existing != bytes {
            bail!("refuse_to_overwrite_different_artifact:{}", path.display());
        }
        return Ok(());
    }
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).with_context(|| format!("create {}", parent.display()))?;
    }
    fs::write(path, bytes).with_context(|| format!("write {}", path.display()))
}

fn main() -> Result<()> {
    let (paths, report_path, worklist_path, verify) = parse_args()?;
    let artifacts = analyze_support_agreement(&paths)?;
    write_or_verify(&report_path, &serialized(&artifacts.report)?, verify)?;
    write_or_verify(&worklist_path, &serialized(&artifacts.worklist)?, verify)?;
    println!(
        "Support Agreement {}: report={} worklist={}",
        if verify { "verified" } else { "generated" },
        report_path.display(),
        worklist_path.display()
    );
    Ok(())
}
