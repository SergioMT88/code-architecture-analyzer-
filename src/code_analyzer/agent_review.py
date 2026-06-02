"""Agent Review — generates metacognitive prompts for AI coding agents.

This module transforms Intent Learning findings into structured prompts that
force the AI agent to think step by step, with metacognition, considering all
errors found by the Code Architecture Analyzer.

The key insight: users don't know everything about their code, especially in
the AI coding era. The analysis generates an automatic prompt that makes the
agent think deeply about the problems and solutions.

This module provides TWO LAYERS of analysis:
1. Code Quality Issues (coupling, SRP, complexity, etc.)
2. Design Patterns Analysis (pattern detection, quality, anti-patterns)
"""
from __future__ import annotations

import ast
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from code_analyzer.constants import (
    HIGH_CONFIDENCE,
    MEDIUM_CONFIDENCE,
    LOW_CONFIDENCE,
)
from code_analyzer.pattern_advisor import get_pattern_advice
from code_analyzer.pattern_analysis import PatternAnalysis, PatternDetection, analyze_patterns

_log = logging.getLogger(__name__)

# Priority ordering for sorting
PRIORITY_ORDER = {"CRITICA": 0, "ALTA": 1, "MEDIA": 2, "BAIXA": 3}


@dataclass
class ReviewInstruction:
    """Single instruction for the coding agent with metacognitive context."""
    
    priority: str  # CRITICA, ALTA, MEDIA, BAIXA
    file: str
    line: int
    end_line: Optional[int]
    criterion: str
    issue: str
    suggestion: str
    confidence: float
    pattern: Optional[str]  # Strategy, Facade, Template Method, etc.
    code_before: Optional[str]
    code_after: Optional[str]
    reasoning: str  # Why this is a problem
    impact: str  # What happens if not fixed
    dependencies: List[str]  # Other findings related to this one
    
    @property
    def priority_weight(self) -> int:
        return PRIORITY_ORDER.get(self.priority, 4)


@dataclass
class AgentReviewPrompt:
    """Complete prompt structure for the AI coding agent.
    
    Contains TWO LAYERS of analysis:
    1. Code Quality Issues (findings with priorities)
    2. Design Patterns Analysis (pattern detection, quality, anti-patterns)
    """
    
    file_path: str
    file_score: float
    file_grade: str
    mi_score: float
    risk_score: float
    total_findings: int
    instructions: List[ReviewInstruction]
    summary: str
    execution_order: List[str]
    metacognition_guide: str
    # Layer 2: Design Patterns
    pattern_analysis: Optional[PatternAnalysis] = None
    pattern_summary: str = ""
    pattern_execution_order: List[str] = field(default_factory=list)
    
    def to_markdown(self) -> str:
        """Generate the complete metacognitive prompt in Markdown with TWO LAYERS."""
        lines = []
        
        # Header
        lines.append("# 🧠 CODE REVIEW — Metacognitive Analysis")
        lines.append("")
        lines.append(f"**File**: `{self.file_path}`")
        lines.append(f"**Score**: {self.file_score}/10 ({self.file_grade})")
        lines.append(f"**Maintainability Index**: {self.mi_score}")
        lines.append(f"**Production Risk**: {self.risk_score}/100")
        lines.append(f"**Total Findings**: {self.total_findings}")
        if self.pattern_analysis:
            lines.append(f"**Patterns Detected**: {self.pattern_analysis.total_detected}")
            lines.append(f"**Anti-patterns Found**: {self.pattern_analysis.total_anti_patterns}")
            lines.append(f"**Pattern Quality**: {self.pattern_analysis.overall_quality}/10")
        lines.append("")
        
        # Metacognition Guide
        lines.append("---")
        lines.append("")
        lines.append("## 🧠 METACOGNITIVE GUIDE — Think Before You Code")
        lines.append("")
        lines.append(self.metacognition_guide)
        lines.append("")
        
        # Summary
        lines.append("---")
        lines.append("")
        lines.append("## 📊 EXECUTIVE SUMMARY")
        lines.append("")
        lines.append(self.summary)
        lines.append("")
        
        # Execution Order
        lines.append("---")
        lines.append("")
        lines.append("## 🎯 EXECUTION ORDER — Fix in This Sequence")
        lines.append("")
        for i, step in enumerate(self.execution_order, 1):
            lines.append(f"{i}. {step}")
        lines.append("")
        
        # ============================================================================
        # LAYER 1: Code Quality Issues
        # ============================================================================
        lines.append("---")
        lines.append("")
        lines.append("# 📊 CAMADA 1: CODE QUALITY ISSUES")
        lines.append("")
        
        # Group instructions by priority
        by_priority: Dict[str, List[ReviewInstruction]] = {}
        for inst in self.instructions:
            by_priority.setdefault(inst.priority, []).append(inst)
        
        for priority in ["CRITICA", "ALTA", "MEDIA", "BAIXA"]:
            if priority not in by_priority:
                continue
            
            emoji = {"CRITICA": "🔴", "ALTA": "🟠", "MEDIA": "🟡", "BAIXA": "🟢"}[priority]
            lines.append(f"## {emoji} {priority} Priority")
            lines.append("")
            
            for inst in by_priority[priority]:
                lines.extend(self._format_instruction(inst))
        
        # ============================================================================
        # LAYER 2: Design Patterns Analysis
        # ============================================================================
        if self.pattern_analysis and self.pattern_analysis.patterns:
            lines.append("---")
            lines.append("")
            lines.append("# 🏗️ CAMADA 2: DESIGN PATTERNS ANALYSIS")
            lines.append("")
            
            # Pattern Summary Table
            lines.append("## Patterns Detected")
            lines.append("")
            lines.append("| Pattern | Status | Location | Quality | Confidence |")
            lines.append("|---------|--------|----------|---------|------------|")
            
            for pattern in self.pattern_analysis.patterns:
                if pattern.detected:
                    status = "✅ IMPLEMENTED"
                    quality = f"{pattern.quality_score}/10"
                    location = pattern.location or "-"
                    confidence = f"{pattern.confidence:.0%}"
                    lines.append(f"| {pattern.pattern} | {status} | {location} | {quality} | {confidence} |")
            
            lines.append("")
            
            # Pattern Quality Checks
            lines.append("## Pattern Quality Checks")
            lines.append("")
            
            for pattern in self.pattern_analysis.patterns:
                if pattern.detected and pattern.checks:
                    status_emoji = "✅" if pattern.quality_score >= 7 else "⚠️" if pattern.quality_score >= 4 else "❌"
                    lines.append(f"### [{pattern.pattern}] {pattern.location or ''}")
                    lines.append(f"**Status**: {status_emoji} — Quality: {pattern.quality_score}/10")
                    lines.append("")
                    
                    lines.append("**Checks**:")
                    for check in pattern.checks:
                        check_emoji = "✅" if check.status == "OK" else "❌"
                        lines.append(f"- {check_emoji} {check.name}: {check.description}")
                    lines.append("")
            
            # Anti-patterns Detected
            anti_patterns = []
            for pattern in self.pattern_analysis.patterns:
                anti_patterns.extend(pattern.anti_patterns)
            
            if anti_patterns:
                lines.append("## Anti-patterns Detected")
                lines.append("")
                lines.append("| Pattern | Anti-pattern | Severity | Issue | Fix |")
                lines.append("|---------|--------------|----------|-------|-----|")
                
                for ap in anti_patterns:
                    severity_emoji = {"ALTA": "🔴", "MEDIA": "🟡", "BAIXA": "🟢"}.get(ap.severity, "")
                    lines.append(f"| {ap.pattern} | {ap.anti_pattern} | {severity_emoji} {ap.severity} | {ap.issue[:50]}... | {ap.fix[:50]}... |")
                
                lines.append("")
            
            # Pattern Suggestions (from pattern_advisor)
            suggestions = self._generate_pattern_suggestions()
            if suggestions:
                lines.append("## Pattern Suggestions")
                lines.append("")
                lines.append("Based on code structure, these patterns would improve architecture:")
                lines.append("")
                
                for i, suggestion in enumerate(suggestions[:3], 1):
                    lines.append(f"{i}. **{suggestion['pattern']} Pattern** — {suggestion.get('location', '')}")
                    lines.append(f"   > {suggestion['suggestion']}")
                    lines.append("")
        
        # Final Checklist
        lines.append("---")
        lines.append("")
        lines.append("## ✅ VERIFICATION CHECKLIST")
        lines.append("")
        lines.append("After fixing, verify:")
        lines.append("")
        lines.append("- [ ] All CRITICAL issues fixed")
        lines.append("- [ ] No new syntax errors introduced")
        lines.append("- [ ] Existing tests still pass")
        lines.append("- [ ] Code follows the patterns suggested")
        lines.append("- [ ] Design patterns are correctly implemented")
        lines.append("- [ ] No anti-patterns detected")
        lines.append("- [ ] Run `code-analyze check` to verify improvement")
        lines.append("")
        
        return "\n".join(lines)
    
    def _format_instruction(self, inst: ReviewInstruction) -> List[str]:
        """Format a single instruction with full context."""
        lines = []
        
        lines.append(f"### [{inst.criterion}] Line {inst.line}" + 
                     (f"-{inst.end_line}" if inst.end_line else ""))
        lines.append("")
        lines.append(f"**Problem**: {inst.issue}")
        lines.append(f"**Confidence**: {inst.confidence:.0%}")
        lines.append(f"**File**: `{inst.file}:{inst.line}`")
        lines.append("")
        
        # Reasoning (metacognition)
        lines.append("**🤔 Why is this a problem?**")
        lines.append(f"> {inst.reasoning}")
        lines.append("")
        
        # Impact
        lines.append("**⚡ Impact if not fixed:**")
        lines.append(f"> {inst.impact}")
        lines.append("")
        
        # Pattern suggestion
        if inst.pattern:
            lines.append(f"**📐 Suggested Pattern**: `{inst.pattern}`")
            lines.append("")
        
        # Code example
        if inst.code_before and inst.code_after:
            lines.append("**🔄 Code Transformation:**")
            lines.append("")
            lines.append("```python")
            lines.append("# ❌ Before")
            lines.append(inst.code_before)
            lines.append("```")
            lines.append("")
            lines.append("```python")
            lines.append("# ✅ After")
            lines.append(inst.code_after)
            lines.append("```")
            lines.append("")
        else:
            lines.append(f"**💡 Suggestion**: {inst.suggestion}")
            lines.append("")
        
        # Dependencies
        if inst.dependencies:
            lines.append(f"**🔗 Related Issues**: {', '.join(inst.dependencies)}")
            lines.append("")
        
        lines.append("---")
        lines.append("")
        
        return lines
    
    def _generate_pattern_suggestions(self) -> List[Dict[str, Any]]:
        """Generate pattern suggestions based on code quality issues."""
        suggestions = []
        
        # Analyze instructions for pattern suggestions
        for inst in self.instructions:
            if inst.pattern and inst.priority in ["CRITICA", "ALTA"]:
                suggestions.append({
                    "pattern": inst.pattern,
                    "location": f"Line {inst.line}",
                    "suggestion": inst.suggestion,
                })
        
        # Add suggestions based on common issues
        critical_count = sum(1 for i in self.instructions if i.priority == "CRITICA")
        high_count = sum(1 for i in self.instructions if i.priority == "ALTA")
        
        if critical_count > 0 or high_count > 3:
            suggestions.append({
                "pattern": "Facade",
                "location": "Module level",
                "suggestion": "Consider creating a Facade to simplify complex subsystem interactions",
            })
        
        return suggestions


class AgentReviewGenerator:
    """Generates metacognitive prompts for AI coding agents.
    
    This class transforms analysis findings into structured prompts that
    force the agent to think step by step, with metacognition, considering
    all errors found.
    """
    
    def __init__(self, intent_store: Optional[Any] = None):
        """Initialize with optional IntentStore for reading user responses."""
        self._intent_store = intent_store
    
    def generate_review(
        self,
        analysis_result: Dict[str, Any],
        file_path: str,
        source_code: Optional[str] = None,
    ) -> AgentReviewPrompt:
        """Generate a complete metacognitive review prompt with TWO LAYERS.
        
        Args:
            analysis_result: Output from run_analysis() or pipeline
            file_path: Path to the analyzed file
            source_code: Optional source code for generating before/after examples
            
        Returns:
            AgentReviewPrompt with all instructions and metacognitive context
        """
        # Extract data from analysis
        criteria = analysis_result.get("criteria", {})
        metrics = analysis_result.get("metrics", {})
        risk = analysis_result.get("production_risk", {})
        
        # Calculate overall metrics
        scores = [v.get("score", 0) for v in criteria.values()]
        file_score = round(sum(scores) / max(1, len(scores)), 1)
        file_grade = self._score_to_grade(file_score)
        mi_score = metrics.get("maintainability_index", 0)
        risk_score = risk.get("score", 0)
        
        # Generate instructions from findings (Layer 1: Code Quality)
        instructions = []
        for criterion_name, criterion_data in criteria.items():
            findings = criterion_data.get("findings", [])
            severity = criterion_data.get("severity", "MEDIA")
            
            for finding in findings:
                inst = self._create_instruction(
                    criterion=criterion_name,
                    finding=finding,
                    severity=severity,
                    file_path=file_path,
                    source_code=source_code,
                    all_criteria=criteria,
                )
                if inst:
                    instructions.append(inst)
        
        # Sort by priority, then by line number
        instructions.sort(key=lambda x: (x.priority_weight, x.line))
        
        # Generate Layer 2: Design Patterns Analysis
        pattern_analysis = None
        pattern_summary = ""
        pattern_execution_order = []
        
        if source_code:
            try:
                tree = ast.parse(source_code)
                pattern_analysis = analyze_patterns(tree, source_code, file_path)
                
                if pattern_analysis and pattern_analysis.patterns:
                    pattern_summary = self._generate_pattern_summary(pattern_analysis)
                    pattern_execution_order = self._generate_pattern_execution_order(pattern_analysis)
            except Exception as e:
                _log.debug("Pattern analysis failed: %s", e, exc_info=True)
        
        # Generate metacognitive guide (updated to include both layers)
        metacognition_guide = self._generate_metacognition_guide(
            instructions=instructions,
            file_score=file_score,
            mi_score=mi_score,
            pattern_analysis=pattern_analysis,
        )
        
        # Generate summary
        summary = self._generate_summary(
            instructions=instructions,
            file_score=file_score,
            file_grade=file_grade,
        )
        
        # Generate execution order (combining both layers)
        execution_order = self._generate_execution_order(instructions)
        execution_order.extend(pattern_execution_order[:3])  # Add top 3 pattern fixes
        
        return AgentReviewPrompt(
            file_path=file_path,
            file_score=file_score,
            file_grade=file_grade,
            mi_score=mi_score,
            risk_score=risk_score,
            total_findings=len(instructions),
            instructions=instructions,
            summary=summary,
            execution_order=execution_order,
            metacognition_guide=metacognition_guide,
            pattern_analysis=pattern_analysis,
            pattern_summary=pattern_summary,
            pattern_execution_order=pattern_execution_order,
        )
    
    def _create_instruction(
        self,
        criterion: str,
        finding: Dict[str, Any],
        severity: str,
        file_path: str,
        source_code: Optional[str],
        all_criteria: Dict[str, Any],
    ) -> Optional[ReviewInstruction]:
        """Create a ReviewInstruction from a finding."""
        try:
            # Check if this finding was confirmed as false positive
            finding_id = finding.get("finding_id", "")
            if self._intent_store and self._intent_store.get(finding_id):
                intent = self._intent_store.get(finding_id)
                if intent.get("answer") in ("intentional", "other_mechanism"):
                    return None  # Skip false positives
            
            # Extract location info
            location = finding.get("location", "")
            line = finding.get("line", 0)
            end_line = finding.get("end_line")
            
            # Parse line from location if not provided
            if not line and location:
                line = self._parse_line_from_location(location)
            
            # Get code context
            code_before = None
            code_after = None
            if source_code and line:
                code_before = self._extract_code_context(source_code, line)
                code_after = self._generate_code_suggestion(
                    criterion=criterion,
                    finding=finding,
                    code_before=code_before,
                )
            
            # Get pattern advice
            pattern = None
            try:
                pattern_advice = get_pattern_advice([finding])
                if pattern_advice:
                    pattern = pattern_advice[0].get("pattern")
            except Exception:
                pass  # Pattern advisor might fail for some findings
            
            # Generate reasoning and impact
            reasoning = self._generate_reasoning(criterion, finding)
            impact = self._generate_impact(criterion, finding, severity)
            
            # Find related findings
            dependencies = self._find_dependencies(
                criterion=criterion,
                finding=finding,
                all_criteria=all_criteria,
            )
            
            # Get confidence
            confidence = finding.get("confidence", 0.8)
            
            return ReviewInstruction(
                priority=severity,
                file=file_path,
                line=line,
                end_line=end_line,
                criterion=criterion,
                issue=finding.get("issue", ""),
                suggestion=finding.get("suggestion", ""),
                confidence=confidence,
                pattern=pattern,
                code_before=code_before,
                code_after=code_after,
                reasoning=reasoning,
                impact=impact,
                dependencies=dependencies,
            )
        except Exception as e:
            _log.debug("Failed to create instruction: %s", e, exc_info=True)
            return None
    
    def _parse_line_from_location(self, location: str) -> int:
        """Extract line number from location string."""
        import re
        match = re.search(r"linha\s+(\d+)", location)
        if match:
            return int(match.group(1))
        match = re.search(r"line\s+(\d+)", location)
        if match:
            return int(match.group(1))
        return 0
    
    def _extract_code_context(self, source_code: str, line: int, context_lines: int = 5) -> str:
        """Extract code context around a line."""
        lines = source_code.split("\n")
        start = max(0, line - context_lines - 1)
        end = min(len(lines), line + context_lines)
        return "\n".join(lines[start:end])
    
    def _generate_code_suggestion(
        self,
        criterion: str,
        finding: Dict[str, Any],
        code_before: str,
    ) -> Optional[str]:
        """Generate a code suggestion based on the criterion."""
        # This is a simplified version - in production, you'd have more sophisticated logic
        
        suggestion_map = {
            "PrintLeak": "logger.debug()",
            "WildcardImport": "from module import specific_name",
            "ManualAccumulate": "[x for x in collection if condition]",
            "DictGet": "dict.get(key, default)",
            "DeepNesting": "Extract to separate function",
            "MagicNumbers": "Use named constant",
        }
        
        replacement = suggestion_map.get(criterion)
        if replacement and code_before:
            # Simple placeholder replacement
            return code_before.replace("# ...", f"# {replacement}")
        
        return None
    
    def _generate_reasoning(self, criterion: str, finding: Dict[str, Any]) -> str:
        """Metacognitive reasoning — delegates to the shared knowledge base so
        the JSON agent output and this Markdown review stay in sync."""
        from code_analyzer.agent_metacognition import reasoning_for
        return reasoning_for(criterion)

    def _generate_impact(
        self,
        criterion: str,
        finding: Dict[str, Any],
        severity: str,
    ) -> str:
        """Impact description — delegates to the shared knowledge base."""
        from code_analyzer.agent_metacognition import impact_for
        return impact_for(criterion, severity)
    
    def _find_dependencies(
        self,
        criterion: str,
        finding: Dict[str, Any],
        all_criteria: Dict[str, Any],
    ) -> List[str]:
        """Find related findings that depend on each other."""
        dependencies = []
        
        # Simple heuristic: findings in the same file with related criteria
        related_criteria = {
            "SRP": ["GodClass", "Cohesion"],
            "GodClass": ["SRP", "Coupling"],
            "Coupling": ["GodClass", "Cohesion"],
            "DeepNesting": ["ManyParameters"],
        }
        
        related = related_criteria.get(criterion, [])
        for rel_criterion in related:
            if rel_criterion in all_criteria:
                rel_findings = all_criteria[rel_criterion].get("findings", [])
                for rel_finding in rel_findings:
                    if rel_finding.get("line") == finding.get("line"):
                        dependencies.append(f"{rel_criterion} (line {rel_finding.get('line')})")
        
        return dependencies
    
    def _generate_metacognition_guide(
        self,
        instructions: List[ReviewInstruction],
        file_score: float,
        mi_score: float,
        pattern_analysis: Optional[PatternAnalysis] = None,
    ) -> str:
        """Generate the metacognitive thinking guide with BOTH LAYERS."""
        critical_count = sum(1 for i in instructions if i.priority == "CRITICA")
        high_count = sum(1 for i in instructions if i.priority == "ALTA")
        
        # Pattern stats
        patterns_detected = 0
        anti_patterns_found = 0
        if pattern_analysis:
            patterns_detected = pattern_analysis.total_detected
            anti_patterns_found = pattern_analysis.total_anti_patterns
        
        guide = """Before fixing any code, think step by step:

**Step 1: Understand Code Quality Issues (CAMADA 1)**
- The file has a score of {file_score}/10 (grade: {grade})
- Maintainability Index is {mi_score} (lower = harder to maintain)
- There are {critical} critical issues that MUST be fixed first
- There are {high} high-priority issues that should be fixed this sprint

**Step 2: Understand Design Patterns (CAMADA 2)**
- {patterns} design patterns detected in this file
- {anti_patterns} anti-patterns found that need attention
- Check if patterns are correctly implemented
- Identify missing patterns that would improve architecture

**Step 3: Prioritize Your Approach**
- Fix CRITICAL code quality issues first - they cause bugs
- Then address anti-patterns - they make code fragile
- Then implement missing patterns - they improve architecture
- MEDIUM and LOW can be fixed when convenient

**Step 4: Think About Dependencies**
- Some findings are related (see "Related Issues" in each instruction)
- Fixing one might resolve others
- Look for patterns: if you see multiple coupling issues, consider a Facade

**Step 5: Verify Your Understanding**
- Read the "Why is this a problem?" section for each finding
- Check the "Pattern Quality Checks" for implementation issues
- Understand the impact before making changes

**Step 6: Apply the Fix**
- Follow the code transformation examples
- Use the suggested patterns (Strategy, Facade, etc.)
- Ensure patterns are correctly implemented (check quality checks)
- Keep changes minimal and focused

**Step 7: Verify the Fix**
- Run the analyzer again to confirm improvement
- Check that no anti-patterns were introduced
- Verify that existing tests still pass
""".format(
            file_score=file_score,
            grade=self._score_to_grade(file_score),
            mi_score=mi_score,
            critical=critical_count,
            high=high_count,
            patterns=patterns_detected,
            anti_patterns=anti_patterns_found,
        )
        
        return guide
    
    def _generate_summary(
        self,
        instructions: List[ReviewInstruction],
        file_score: float,
        file_grade: str,
    ) -> str:
        """Generate executive summary."""
        by_priority = {}
        for inst in instructions:
            by_priority.setdefault(inst.priority, []).append(inst)
        
        summary = f"**Overall Assessment**: {file_score}/10 ({file_grade})\n\n"
        summary += "**Issues by Priority**:\n"
        
        for priority in ["CRITICA", "ALTA", "MEDIA", "BAIXA"]:
            count = len(by_priority.get(priority, []))
            if count > 0:
                emoji = {"CRITICA": "🔴", "ALTA": "🟠", "MEDIA": "🟡", "BAIXA": "🟢"}[priority]
                summary += f"- {emoji} {priority}: {count} issues\n"
        
        summary += "\n**Top Issues**:\n"
        for inst in instructions[:3]:
            summary += f"- [{inst.criterion}] Line {inst.line}: {inst.issue[:60]}...\n"
        
        return summary
    
    def _generate_execution_order(self, instructions: List[ReviewInstruction]) -> List[str]:
        """Generate recommended execution order."""
        order = []
        
        # Group by priority
        by_priority = {}
        for inst in instructions:
            by_priority.setdefault(inst.priority, []).append(inst)
        
        # CRITICAL first
        for inst in by_priority.get("CRITICA", []):
            order.append(f"Fix [{inst.criterion}] at line {inst.line}")
        
        # Then HIGH
        for inst in by_priority.get("ALTA", []):
            order.append(f"Fix [{inst.criterion}] at line {inst.line}")
        
        # Then MEDIUM
        for inst in by_priority.get("MEDIA", [])[:3]:  # Limit to top 3
            order.append(f"Fix [{inst.criterion}] at line {inst.line}")
        
        if not order:
            order.append("No issues to fix - code looks good!")
        
        return order
    
    def _generate_pattern_summary(self, pattern_analysis: PatternAnalysis) -> str:
        """Generate a summary of pattern analysis."""
        if not pattern_analysis or not pattern_analysis.patterns:
            return ""
        
        detected = [p for p in pattern_analysis.patterns if p.detected]
        
        summary = f"**Patterns Detected**: {len(detected)}\n\n"
        
        for pattern in detected:
            status = "✅" if pattern.quality_score >= 7 else "⚠️" if pattern.quality_score >= 4 else "❌"
            summary += f"- {status} **{pattern.pattern}**: {pattern.location or 'Unknown'} (Quality: {pattern.quality_score}/10)\n"
        
        if pattern_analysis.total_anti_patterns > 0:
            summary += f"\n**Anti-patterns Found**: {pattern_analysis.total_anti_patterns}\n"
            for pattern in detected:
                for ap in pattern.anti_patterns:
                    summary += f"- ⚠️ {ap.pattern}: {ap.anti_pattern}\n"
        
        return summary
    
    def _generate_pattern_execution_order(self, pattern_analysis: PatternAnalysis) -> List[str]:
        """Generate execution order for pattern fixes."""
        order = []
        
        if not pattern_analysis or not pattern_analysis.patterns:
            return order
        
        # First: fix anti-patterns
        for pattern in pattern_analysis.patterns:
            for ap in pattern.anti_patterns:
                if ap.severity == "ALTA":
                    order.append(f"Fix anti-pattern [{ap.pattern}: {ap.anti_pattern}] at line {ap.line}")
        
        # Then: implement missing patterns
        for pattern in pattern_analysis.patterns:
            if not pattern.detected and pattern.suggestion:
                order.append(f"Consider implementing {pattern.pattern}: {pattern.suggestion}")
        
        return order
    
    def _score_to_grade(self, score: float) -> str:
        """Convert score to grade."""
        if score >= 9:
            return "A"
        if score >= 7:
            return "B"
        if score >= 5:
            return "C"
        return "D"


def generate_agent_prompt(
    analysis_result: Dict[str, Any],
    file_path: str,
    source_code: Optional[str] = None,
    intent_store: Optional[Any] = None,
) -> str:
    """Convenience function to generate an agent review prompt.
    
    Args:
        analysis_result: Output from run_analysis() or pipeline
        file_path: Path to the analyzed file
        source_code: Optional source code for generating before/after examples
        intent_store: Optional IntentStore for reading user responses
        
    Returns:
        Markdown string with the complete metacognitive prompt
    """
    generator = AgentReviewGenerator(intent_store=intent_store)
    review = generator.generate_review(
        analysis_result=analysis_result,
        file_path=file_path,
        source_code=source_code,
    )
    markdown = review.to_markdown()

    # Add suggested diffs if source code is available
    if source_code:
        try:
            from code_analyzer.analyzer.diff_generation import generate_all_diffs
            import ast as _ast
            tree = _ast.parse(source_code)
            diffs = generate_all_diffs(tree, source_code, file_path)
            if diffs:
                diff_lines = ["", "---", "", "## 🔧 SUGGESTED DIFFS — Mechanical Patterns", ""]
                diff_lines.append("| # | Pattern | Line | Before | After | Confidence |")
                diff_lines.append("|---|---------|------|--------|-------|------------|")
                for i, d in enumerate(diffs, 1):
                    diff_lines.append(
                        f"| {i} | {d.pattern} | {d.line} | "
                        f"`{d.before[:50]}` | `{d.after[:50]}` | "
                        f"{int(d.confidence*100)}% |"
                    )
                diff_lines.append("")
                diff_lines.append("**Apply these diffs before making structural changes — they are safe and mechanical.**")
                diff_lines.append("")

                # Insert before verification checklist
                checklist_marker = "## ✅ VERIFICATION CHECKLIST"
                idx = markdown.find(checklist_marker)
                if idx > 0:
                    markdown = markdown[:idx] + "\n".join(diff_lines) + "\n\n" + markdown[idx:]
                else:
                    markdown += "\n" + "\n".join(diff_lines)
        except Exception:
            pass

    return markdown