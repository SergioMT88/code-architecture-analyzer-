#!/usr/bin/env python3
"""
Report Generator - Gera relatórios JSON e Markdown
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import sys

class ReportGenerator:
    """Gera relatórios estruturados"""

    def __init__(self, filepath: str, analysis: Dict[str, Any]):
        self.filepath = Path(filepath)
        self.analysis = analysis
        self.timestamp = datetime.now().isoformat()

    def generate_json_report(self) -> Dict[str, Any]:
        """Gera relatório JSON"""
        return {
            "metadata": {
                "timestamp": self.timestamp,
                "file_analyzed": str(self.filepath),
                "tool": "Code Architecture Analyzer v1.0"
            },
            "metrics": self.analysis.get("metrics", {}),
            "criteria": self.analysis.get("criteria", {}),
            "recommendations": self._generate_recommendations()
        }

    def generate_markdown_report(self) -> str:
        """Gera relatório Markdown"""
        lines = []
        lines.append("# Relatório de Análise de Arquitetura Python\n")
        lines.append(f"**Data:** {self.timestamp}\n")
        lines.append(f"**Arquivo:** `{self.filepath.name}`\n")

        # Métricas
        lines.append("## 📊 Métricas\n")
        metrics = self.analysis.get("metrics", {})
        lines.append(f"- Linhas de código: {metrics.get('lines_of_code')}")
        lines.append(f"- Classes: {metrics.get('num_classes')}")
        lines.append(f"- Funções: {metrics.get('num_functions')}")
        lines.append(f"- Imports: {metrics.get('num_imports')}\n")

        # Critérios
        lines.append("## 🎯 Análise por Critério\n")
        criteria = self.analysis.get("criteria", {})

        for criterion_key, criterion in criteria.items():
            score = criterion.get("score", 0)
            status = criterion.get("status", "N/A")
            findings = criterion.get("findings", [])

            lines.append(f"### {criterion_key}")
            lines.append(f"**Score:** {score}/10 | {status}\n")

            if findings:
                lines.append("**Problemas encontrados:**")
                for finding in findings[:3]:
                    lines.append(f"- {finding.get('issue')}")
                lines.append("")
            else:
                lines.append("✅ Sem problemas\n")

        # Recomendações
        lines.append("## 💡 Recomendações\n")
        recommendations = self._generate_recommendations()
        for i, rec in enumerate(recommendations[:5], 1):
            lines.append(f"{i}. {rec['title']}")
            lines.append(f"   - {rec['description']}\n")

        return "\n".join(lines)

    def _generate_recommendations(self) -> list:
        """Gera recomendações baseado na análise"""
        recommendations = []
        criteria = self.analysis.get("criteria", {})

        for criterion_key, criterion in criteria.items():
            score = criterion.get("score", 0)

            if score < 5:
                recommendations.append({
                    "title": f"🔴 CRÍTICO: {criterion_key}",
                    "description": f"Score {score}/10 - Refatoração urgente necessária",
                    "priority": "ALTA"
                })
            elif score < 8:
                recommendations.append({
                    "title": f"🟡 MELHORAR: {criterion_key}",
                    "description": f"Score {score}/10 - Oportunidade de melhoria",
                    "priority": "MÉDIA"
                })

        recommendations.sort(key=lambda x: {"ALTA": 0, "MÉDIA": 1, "BAIXA": 2}.get(x["priority"], 3))
        return recommendations

    def save_reports(self, output_dir: str = None) -> Dict[str, str]:
        """Salva relatórios em arquivos"""
        if output_dir is None:
            output_dir = self.filepath.parent
        else:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

        output_dir = Path(output_dir)

        # Salvar JSON
        json_path = output_dir / f"{self.filepath.stem}_analysis.json"
        json_report = self.generate_json_report()
        json_path.write_text(json.dumps(json_report, indent=2, default=str))

        # Salvar Markdown
        md_path = output_dir / f"{self.filepath.stem}_report.md"
        md_report = self.generate_markdown_report()
        md_path.write_text(md_report)

        return {
            "json_report": str(json_path),
            "markdown_report": str(md_path)
        }

def generate_reports(filepath: str, analysis: Dict[str, Any], output_dir: str = None) -> Dict[str, str]:
    """Função principal"""
    try:
        generator = ReportGenerator(filepath, analysis)
        return generator.save_reports(output_dir)
    except Exception as e:
        return {"error": f"Erro ao gerar relatórios: {e}"}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python report_generator.py <arquivo.py>")
        sys.exit(1)

    # Análise dummy para teste
    analysis = {
        "metrics": {"lines_of_code": 100, "num_classes": 2, "num_functions": 5, "num_imports": 3},
        "criteria": {}
    }

    result = generate_reports(sys.argv[1], analysis)
    print(json.dumps(result, indent=2))
