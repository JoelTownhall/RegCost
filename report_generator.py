"""
PDF Report Generator for Regulatory Burden Analysis.

Creates a one-page professional PDF report comparing BC and RegData methodologies.
"""
import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import numpy as np

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

import config

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates PDF report comparing BC and RegData methodologies."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or config.OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Set up custom paragraph styles."""
        self.styles.add(ParagraphStyle(
            name='ReportTitle',
            parent=self.styles['Title'],
            fontSize=18,
            spaceAfter=6*mm,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#1a1a2e')
        ))

        self.styles.add(ParagraphStyle(
            name='ReportSubtitle',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=4*mm,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#4a4a4a')
        ))

        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=12,
            spaceBefore=4*mm,
            spaceAfter=2*mm,
            textColor=colors.HexColor('#2E86AB')
        ))

        self.styles.add(ParagraphStyle(
            name='ReportBody',
            parent=self.styles['Normal'],
            fontSize=9,
            spaceAfter=2*mm,
            leading=12
        ))

        self.styles.add(ParagraphStyle(
            name='SmallText',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#666666')
        ))

    def create_comparison_chart(self, bc_total: int, regdata_total: int,
                                 filepath: Optional[Path] = None) -> Path:
        """Create a bar chart comparing BC and RegData totals."""
        filepath = filepath or (self.output_dir / 'comparison_chart.png')

        fig, ax = plt.subplots(figsize=(6, 3.5), dpi=150)

        methods = ['BC Method\n(Requirements)', 'RegData Method\n(Restrictions)']
        values = [bc_total, regdata_total]
        colors_list = [config.CHART_COLORS['bc_method'], config.CHART_COLORS['regdata_method']]

        bars = ax.bar(methods, values, color=colors_list, width=0.5, edgecolor='white', linewidth=1.5)

        # Add value labels on bars
        for bar, val in zip(bars, values):
            height = bar.get_height()
            ax.annotate(f'{val:,}',
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 5),
                       textcoords="offset points",
                       ha='center', va='bottom',
                       fontsize=12, fontweight='bold')

        ax.set_ylabel('Count', fontsize=10)
        ax.set_title('Regulatory Burden Comparison', fontsize=12, fontweight='bold', pad=10)

        # Remove top and right spines
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        # Add grid
        ax.yaxis.grid(True, linestyle='--', alpha=0.7)
        ax.set_axisbelow(True)

        plt.tight_layout()
        plt.savefig(filepath, bbox_inches='tight', facecolor='white')
        plt.close()

        logger.info(f"Created comparison chart: {filepath}")
        return filepath

    def create_department_chart(self, bc_by_dept: Dict, regdata_by_dept: Dict,
                                 filepath: Optional[Path] = None) -> Path:
        """Create a horizontal bar chart showing burden by department."""
        filepath = filepath or (self.output_dir / 'department_chart.png')

        # Get top 8 departments by BC count
        dept_totals = {}
        for dept, data in bc_by_dept.items():
            dept_totals[dept] = data.get('count', 0) if isinstance(data, dict) else data

        top_depts = sorted(dept_totals.items(), key=lambda x: x[1], reverse=True)[:8]
        departments = [d[0] for d in top_depts]

        bc_values = [dept_totals.get(d, 0) for d in departments]
        regdata_values = []
        for d in departments:
            rd_data = regdata_by_dept.get(d, {})
            regdata_values.append(rd_data.get('count', 0) if isinstance(rd_data, dict) else rd_data)

        fig, ax = plt.subplots(figsize=(6, 4), dpi=150)

        y = np.arange(len(departments))
        height = 0.35

        bars1 = ax.barh(y - height/2, bc_values, height, label='BC Method',
                       color=config.CHART_COLORS['bc_method'])
        bars2 = ax.barh(y + height/2, regdata_values, height, label='RegData Method',
                       color=config.CHART_COLORS['regdata_method'])

        ax.set_xlabel('Count', fontsize=10)
        ax.set_title('Regulatory Burden by Department', fontsize=12, fontweight='bold', pad=10)
        ax.set_yticks(y)
        ax.set_yticklabels(departments, fontsize=8)
        ax.legend(loc='lower right', fontsize=8)

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.xaxis.grid(True, linestyle='--', alpha=0.7)
        ax.set_axisbelow(True)

        plt.tight_layout()
        plt.savefig(filepath, bbox_inches='tight', facecolor='white')
        plt.close()

        logger.info(f"Created department chart: {filepath}")
        return filepath

    def generate_report(self, bc_results: Dict, regdata_results: Dict,
                        metadata: Optional[Dict] = None,
                        filepath: Optional[Path] = None) -> Path:
        """
        Generate the one-page PDF report.

        Args:
            bc_results: Results from BCRequirementsCounter.analyze_regulations()
            regdata_results: Results from RegDataRestrictionsCounter.analyze_regulations()
            metadata: Additional metadata (data_source, scope, etc.)
            filepath: Output path for PDF
        """
        filepath = filepath or (self.output_dir / config.REPORT_FILENAME)
        metadata = metadata or {}

        # Create charts
        chart_path = self.create_comparison_chart(
            bc_results['total_requirements'],
            regdata_results['total_restrictions']
        )

        # Build document
        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=A4,
            rightMargin=15*mm,
            leftMargin=15*mm,
            topMargin=12*mm,
            bottomMargin=12*mm
        )

        story = []

        # Header
        story.append(Paragraph(config.REPORT_TITLE, self.styles['ReportTitle']))

        analysis_date = datetime.now().strftime('%d %B %Y')
        subtitle = f"Analysis Date: {analysis_date}"
        if metadata.get('data_source'):
            subtitle += f" | Source: {metadata['data_source']}"
        story.append(Paragraph(subtitle, self.styles['ReportSubtitle']))

        story.append(Spacer(1, 3*mm))

        # Summary Statistics Box
        story.append(Paragraph("Summary Statistics", self.styles['SectionHeader']))

        # Calculate percentage difference
        bc_total = bc_results['total_requirements']
        rd_total = regdata_results['total_restrictions']
        if bc_total > 0:
            pct_diff = ((rd_total - bc_total) / bc_total) * 100
            pct_str = f"+{pct_diff:.1f}%" if pct_diff >= 0 else f"{pct_diff:.1f}%"
        else:
            pct_str = "N/A"

        stats_data = [
            ['Metric', 'Value'],
            ['Total Documents Analyzed', f"{bc_results['regulations_analyzed']:,}"],
            ['BC Method Requirements', f"{bc_total:,}"],
            ['RegData Method Restrictions', f"{rd_total:,}"],
            ['Difference (RegData vs BC)', pct_str],
        ]

        # Add scope info if available
        if metadata.get('scope'):
            stats_data.append(['Scope', metadata['scope']])

        # Check if using sample data
        if metadata.get('is_sample'):
            stats_data.append(['Data Type', 'Sample/Test Data'])

        stats_table = Table(stats_data, colWidths=[60*mm, 50*mm])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
        ]))
        story.append(stats_table)

        story.append(Spacer(1, 4*mm))

        # Comparison Chart
        story.append(Paragraph("Methodology Comparison", self.styles['SectionHeader']))

        img = Image(str(chart_path), width=140*mm, height=75*mm)
        story.append(img)

        story.append(Spacer(1, 3*mm))

        # Top 10 Regulations Table
        story.append(Paragraph("Top 10 Most Burdensome Regulations (BC Method)", self.styles['SectionHeader']))

        top_regs_data = [['Rank', 'Regulation Title', 'Requirements']]
        for i, reg in enumerate(bc_results.get('top_regulations', [])[:10], 1):
            title = reg.get('title', 'Unknown')
            # Truncate long titles
            if len(title) > 60:
                title = title[:57] + '...'
            top_regs_data.append([
                str(i),
                title,
                f"{reg.get('total_requirements', 0):,}"
            ])

        if len(top_regs_data) > 1:
            top_table = Table(top_regs_data, colWidths=[12*mm, 120*mm, 28*mm])
            top_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#A23B72')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (0, -1), 'CENTER'),
                ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fff')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            ]))
            story.append(top_table)
        else:
            story.append(Paragraph("No regulations data available.", self.styles['BodyText']))

        story.append(Spacer(1, 4*mm))

        # Methodology Notes
        story.append(Paragraph("Methodology Notes", self.styles['SectionHeader']))

        bc_note = (
            "<b>BC Method:</b> Counts binding words ('must', 'shall', 'required') that indicate "
            "mandatory obligations. Excludes prohibitions ('must not', 'shall not') and "
            "discretionary language ('may'). Based on British Columbia's regulatory counting approach."
        )
        story.append(Paragraph(bc_note, self.styles['SmallText']))

        story.append(Spacer(1, 1*mm))

        rd_note = (
            "<b>RegData Method:</b> Counts restriction words ('shall', 'must', 'may not', 'required', "
            "'prohibited') following the Mercatus Center/QuantGov methodology. Includes prohibitions, "
            "which accounts for higher counts compared to the BC method."
        )
        story.append(Paragraph(rd_note, self.styles['SmallText']))

        story.append(Spacer(1, 2*mm))

        diff_note = (
            "<b>Expected Differences:</b> The RegData method typically produces higher counts because "
            "it includes prohibitions ('may not', 'prohibited'), while BC method focuses on affirmative "
            "obligations. Both metrics provide valid but different perspectives on regulatory burden."
        )
        story.append(Paragraph(diff_note, self.styles['SmallText']))

        # Footer
        story.append(Spacer(1, 4*mm))

        footer_text = (
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
            f"Data Source: {metadata.get('data_source', 'legislation.gov.au')} | "
            f"Tool: Australian Regulatory Burden Analyzer"
        )
        story.append(Paragraph(footer_text, self.styles['SmallText']))

        # Build PDF
        doc.build(story)

        logger.info(f"Generated report: {filepath}")
        return filepath


def generate_report(bc_results: Dict, regdata_results: Dict,
                   metadata: Optional[Dict] = None,
                   output_path: Optional[Path] = None) -> Path:
    """Convenience function to generate a report."""
    generator = ReportGenerator()
    return generator.generate_report(bc_results, regdata_results, metadata, output_path)


if __name__ == "__main__":
    # Test report generation with sample data
    sample_bc_results = {
        'total_requirements': 125000,
        'total_regulations': 450,
        'regulations_analyzed': 450,
        'by_department': {
            'Treasury': {'count': 25000, 'regulations': 80},
            'Health': {'count': 20000, 'regulations': 60},
            'Education': {'count': 15000, 'regulations': 50},
            'Defence': {'count': 10000, 'regulations': 40},
            'Home Affairs': {'count': 18000, 'regulations': 55},
            'Other': {'count': 37000, 'regulations': 165},
        },
        'by_word': {'must': 60000, 'shall': 45000, 'required': 20000},
        'top_regulations': [
            {'title': 'Financial Framework (Supplementary Powers) Regulations 2015', 'total_requirements': 2500},
            {'title': 'Migration Regulations 1994', 'total_requirements': 2200},
            {'title': 'Therapeutic Goods Regulations 1990', 'total_requirements': 1800},
            {'title': 'Customs Regulations 2015', 'total_requirements': 1500},
            {'title': 'Work Health and Safety Regulations 2011', 'total_requirements': 1400},
            {'title': 'Aviation Safety Regulations 1998', 'total_requirements': 1300},
            {'title': 'Income Tax Assessment Regulations 1997', 'total_requirements': 1200},
            {'title': 'Environmental Protection Regulations 2000', 'total_requirements': 1100},
            {'title': 'Corporations Regulations 2001', 'total_requirements': 1000},
            {'title': 'Privacy Regulations 2013', 'total_requirements': 900},
        ],
        'by_regulation': [],
    }

    sample_regdata_results = {
        'total_restrictions': 140000,
        'total_regulations': 450,
        'regulations_analyzed': 450,
        'by_department': {
            'Treasury': {'count': 28000, 'regulations': 80},
            'Health': {'count': 22000, 'regulations': 60},
            'Education': {'count': 16500, 'regulations': 50},
            'Defence': {'count': 11000, 'regulations': 40},
            'Home Affairs': {'count': 20000, 'regulations': 55},
            'Other': {'count': 42500, 'regulations': 165},
        },
        'by_word': {'must': 60000, 'shall': 45000, 'required': 20000, 'may not': 8000, 'prohibited': 7000},
        'top_regulations': [],
        'by_regulation': [],
    }

    metadata = {
        'data_source': 'legislation.gov.au (Sample Data)',
        'scope': 'Federal Acts and Legislative Instruments - In Force',
        'is_sample': True,
    }

    report_path = generate_report(sample_bc_results, sample_regdata_results, metadata)
    print(f"Test report generated: {report_path}")
