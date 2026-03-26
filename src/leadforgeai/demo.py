"""LeadForgeAI demo workflow using the single GiskardFoundry adapter boundary."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from leadforgeai.integrations.giskard import create_leadforge_agent


def load_sample_opportunities() -> list[dict[str, str]]:
    """Load deterministic sample opportunities for portfolio demo use."""
    return [
        {
            "title": "Senior DevOps Engineer",
            "company": "Contoso",
            "location": "Remote",
            "summary": "Azure IaC, CI/CD, Kubernetes",
        },
        {
            "title": "Cloud AI Platform Engineer",
            "company": "Fabrikam",
            "location": "Hybrid",
            "summary": "MLOps, platform reliability, Python",
        },
    ]


def rank_opportunities(enriched: list[dict[str, object]]) -> list[dict[str, object]]:
    """Apply deterministic ranking for demo purposes only."""
    ranked = []
    for index, item in enumerate(enriched, start=1):
        ranked.append({"rank": index, **item})
    return ranked


def write_csv(rows: list[dict[str, object]], output_path: Path) -> None:
    """Write rows to CSV file."""
    if not rows:
        output_path.write_text("", encoding="utf-8")
        return

    fieldnames = list(rows[0].keys())
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    agent = create_leadforge_agent(context={"source": "demo"})
    raw_ops = load_sample_opportunities()

    enriched = [agent.run(opportunity) for opportunity in raw_ops]
    ranked = rank_opportunities(enriched)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Path(f"leadforgeai_output_{timestamp}.csv")
    write_csv(ranked, output_path)

    print(f"Wrote {len(ranked)} opportunities to {output_path}")


if __name__ == "__main__":
    main()
