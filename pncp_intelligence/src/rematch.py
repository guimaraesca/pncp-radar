"""Reclassificação dos editais já armazenados quando o dicionário (keywords.yaml) muda.

Idempotente: só reprocessa linhas cuja versão do dicionário (`keywords_hash`) difere da vigente,
e carimba a linhagem (versão do dicionário, data da classificação e, para linhas anteriores ao
rastreio, run_id/endpoint 'legacy'). Mantém o mesmo formato de `matched_keywords` do coletor
("termo a, termo b"), ao contrário do script antigo que gravava JSON.

Uso:
    python -m pncp_intelligence.src.rematch            # só linhas desatualizadas
    python -m pncp_intelligence.src.rematch --force    # todas
"""

import argparse
import sys
from typing import Any, Dict, Optional

from pncp_intelligence.src.db import PNCPDatabase
from pncp_intelligence.src.matcher import ThematicMatcher
from pncp_intelligence.src.observability import LEGACY_ENDPOINT, LEGACY_RUN_ID


def rematch_stale(db: PNCPDatabase, matcher: Optional[ThematicMatcher] = None, force: bool = False) -> Dict[str, Any]:
    matcher = matcher or ThematicMatcher()
    fingerprint = matcher.fingerprint()

    with db.get_connection() as conn:
        where = "" if force else "WHERE keywords_hash IS NULL OR keywords_hash != ?"
        rows = conn.execute(
            f"SELECT id, objeto_compra, informacao_complementar, COALESCE(matched_category,'') AS cat "
            f"FROM contratacoes {where}",
            () if force else (fingerprint,),
        ).fetchall()

        gained = lost = kept = 0
        for r in rows:
            is_match, cat, sub, terms = matcher.match(r["objeto_compra"], r["informacao_complementar"])
            had = bool(r["cat"])
            gained += int(is_match and not had)
            lost += int(had and not is_match)
            kept += int(had and is_match)
            conn.execute(
                """UPDATE contratacoes SET
                       matched_category = ?, matched_subtema = ?, matched_keywords = ?,
                       keywords_hash = ?, classified_at = CURRENT_TIMESTAMP,
                       first_run_id = COALESCE(first_run_id, ?),
                       last_run_id = COALESCE(last_run_id, ?),
                       source_endpoint = COALESCE(source_endpoint, ?)
                   WHERE id = ?""",
                (cat, sub, ", ".join(terms), fingerprint,
                 LEGACY_RUN_ID, LEGACY_RUN_ID, LEGACY_ENDPOINT, r["id"]),
            )
        conn.commit()
        total_match = conn.execute(
            "SELECT COUNT(*) FROM contratacoes WHERE COALESCE(matched_category,'') != ''").fetchone()[0]

    return {"keywords_hash": fingerprint, "reprocessed": len(rows), "gained": gained,
            "lost": lost, "kept": kept, "in_scope_now": total_match}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Reclassifica editais com o dicionário vigente.")
    ap.add_argument("--db", default="pncp_intelligence/data/pncp_intelligence.sqlite")
    ap.add_argument("--keywords", default="pncp_intelligence/config/keywords.yaml")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    summary = rematch_stale(PNCPDatabase(args.db), ThematicMatcher(args.keywords), force=args.force)
    print(f"Dicionário {summary['keywords_hash']}: {summary['reprocessed']} linhas reprocessadas "
          f"(+{summary['gained']} entraram, -{summary['lost']} saíram, {summary['kept']} mantidas). "
          f"No escopo agora: {summary['in_scope_now']}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
