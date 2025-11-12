"""
Monitoring and Reporting Module for E2E Testing.

This module provides comprehensive test execution monitoring, performance tracking,
and reporting capabilities for end-to-end testing workflows. It stores metrics in
a SQLite database and generates reports in multiple formats (HTML, JSON, Markdown).

Key Features:
    - Test execution monitoring with detailed metrics
    - Performance metrics collection (execution time, memory, CPU)
    - Multi-format report generation (HTML, JSON, Markdown)
    - Historical trend analysis and performance tracking
    - Automated alert system for failures and degradation
    - Integration points for external monitoring systems

Database Schema:
    The module creates two main tables:
    - test_metrics: Individual test execution data
    - suite_metrics: Aggregated test suite statistics

    Indexes are created on timestamp and suite_name for efficient queries.

Usage Example:
    >>> from pathlib import Path
    >>> metrics_collector = TestMetricsCollector(Path("metrics.db"))
    >>> report_generator = ReportGenerator(metrics_collector)
    >>> alert_system = AlertSystem(metrics_collector)
    >>>
    >>> # Record metrics
    >>> suite_metrics = SuiteMetrics(...)
    >>> metrics_collector.record_suite_metrics(suite_metrics)
    >>>
    >>> # Generate reports
    >>> report_generator.generate_html_report(Path("report.html"))
    >>> alert_system.check_and_send_alerts("suite_name", suite_metrics)
"""

import json
import logging
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class TestMetrics:
    """
    Individual test execution metrics.

    Captures detailed metrics for a single test execution, including
    performance data, resource usage, and outcome information.

    Attributes:
        test_name: Name of the individual test function
        suite_name: Name of the test suite containing this test
        execution_time: Test execution duration in seconds
        memory_peak_mb: Peak memory usage during test execution in megabytes
        cpu_avg_percent: Average CPU utilization percentage during execution
        success: Whether the test passed (True) or failed (False)
        timestamp: ISO 8601 formatted timestamp of test execution
        error_message: Error message if test failed, None if passed
        coverage_percent: Code coverage percentage for this test, if available
    """

    test_name: str
    suite_name: str
    execution_time: float
    memory_peak_mb: float
    cpu_avg_percent: float
    success: bool
    timestamp: str
    error_message: Optional[str] = None
    coverage_percent: Optional[float] = None


@dataclass
class SuiteMetrics:
    """
    Aggregated test suite metrics.

    Contains summary statistics for an entire test suite execution,
    calculated from individual test results.

    Attributes:
        suite_name: Name of the test suite
        total_tests: Total number of tests in the suite
        passed_tests: Number of tests that passed
        failed_tests: Number of tests that failed
        skipped_tests: Number of tests that were skipped
        total_duration: Total execution time for all tests in seconds
        avg_execution_time: Average execution time per test in seconds
        success_rate: Percentage of tests that passed (0-100)
        timestamp: ISO 8601 formatted timestamp of suite execution
        coverage_percent: Overall code coverage percentage for suite, if available
    """

    suite_name: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    total_duration: float
    avg_execution_time: float
    success_rate: float
    timestamp: str
    coverage_percent: Optional[float] = None


@dataclass
class TrendData:
    """
    Performance trend analysis data.

    Captures historical trend information for a specific metric,
    including direction of change and magnitude.

    Attributes:
        metric_name: Name of the metric being analyzed (e.g., 'execution_time', 'success_rate')
        timestamps: List of ISO 8601 formatted timestamps for each data point
        values: List of metric values corresponding to each timestamp
        trend_direction: Direction of trend - one of:
            - "improving": Metric is getting better over time
            - "degrading": Metric is getting worse over time
            - "stable": Metric shows less than 5% change
        change_percent: Percentage change between first and second half of data
            - Positive values indicate increase
            - Negative values indicate decrease
            - Interpretation depends on metric (e.g., execution time increase is bad)
    """

    metric_name: str
    timestamps: List[str]
    values: List[float]
    trend_direction: str  # "improving", "degrading", "stable"
    change_percent: float


class TestMetricsCollector:
    """
    Collects and stores test execution metrics in a SQLite database.

    This class manages the persistence layer for test metrics, providing
    methods to record individual test and suite metrics, retrieve historical
    data, and analyze performance trends over time.

    The database schema includes:
    - test_metrics table: Individual test execution records
    - suite_metrics table: Aggregated suite statistics
    - Indexes on timestamp and suite_name for query performance

    Attributes:
        db_path: Path to SQLite database file
        logger: Logger instance for this class

    Example:
        >>> collector = TestMetricsCollector(Path("metrics.db"))
        >>> metrics = TestMetrics(
        ...     test_name="test_login",
        ...     suite_name="auth_tests",
        ...     execution_time=1.5,
        ...     memory_peak_mb=50.2,
        ...     cpu_avg_percent=25.3,
        ...     success=True,
        ...     timestamp=datetime.now().isoformat()
        ... )
        >>> collector.record_test_metrics(metrics)
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize metrics collector with database connection.

        Args:
            db_path: Path to SQLite database file. Defaults to "test_metrics.db"
                in the current directory if not specified.

        Note:
            Creates database and tables if they don't exist.
        """
        self.db_path = db_path or Path("test_metrics.db")
        self.logger = logging.getLogger(__name__)
        self._init_database()

    def _init_database(self):
        """
        Initialize SQLite database schema and indexes.

        Creates two main tables for storing metrics:
        1. test_metrics: Individual test execution records
        2. suite_metrics: Aggregated suite-level statistics

        Also creates indexes on frequently queried columns to optimize
        performance for historical data retrieval and trend analysis.

        Note:
            Uses CREATE TABLE IF NOT EXISTS to safely handle repeated initializations.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Create test metrics table for individual test execution records
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS test_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_name TEXT NOT NULL,
                    suite_name TEXT NOT NULL,
                    execution_time REAL NOT NULL,
                    memory_peak_mb REAL NOT NULL,
                    cpu_avg_percent REAL NOT NULL,
                    success BOOLEAN NOT NULL,
                    timestamp TEXT NOT NULL,
                    error_message TEXT,
                    coverage_percent REAL
                )
            """
            )

            # Create suite metrics table for aggregated suite-level statistics
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS suite_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    suite_name TEXT NOT NULL,
                    total_tests INTEGER NOT NULL,
                    passed_tests INTEGER NOT NULL,
                    failed_tests INTEGER NOT NULL,
                    skipped_tests INTEGER NOT NULL,
                    total_duration REAL NOT NULL,
                    avg_execution_time REAL NOT NULL,
                    success_rate REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    coverage_percent REAL
                )
            """
            )

            # Create indexes for efficient historical queries
            # Timestamp indexes support date range queries for trend analysis
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_test_timestamp ON test_metrics(timestamp)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_suite_timestamp ON suite_metrics(timestamp)"
            )
            # Suite name index supports filtering by specific test suite
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_test_suite ON test_metrics(suite_name)")

            conn.commit()

    def record_test_metrics(self, metrics: TestMetrics):
        """
        Record individual test execution metrics to database.

        Args:
            metrics: TestMetrics object containing test execution data

        Note:
            This method commits the transaction immediately after insertion.
            All fields from the TestMetrics object are persisted to the database.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO test_metrics (
                    test_name, suite_name, execution_time, memory_peak_mb,
                    cpu_avg_percent, success, timestamp, error_message, coverage_percent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    metrics.test_name,
                    metrics.suite_name,
                    metrics.execution_time,
                    metrics.memory_peak_mb,
                    metrics.cpu_avg_percent,
                    metrics.success,
                    metrics.timestamp,
                    metrics.error_message,
                    metrics.coverage_percent,
                ),
            )
            conn.commit()

    def record_suite_metrics(self, metrics: SuiteMetrics):
        """
        Record aggregated test suite metrics to database.

        Args:
            metrics: SuiteMetrics object containing suite-level statistics

        Note:
            This method commits the transaction immediately after insertion.
            Use this method once per test suite execution to record summary data.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO suite_metrics (
                    suite_name, total_tests, passed_tests, failed_tests, skipped_tests,
                    total_duration, avg_execution_time, success_rate, timestamp, coverage_percent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    metrics.suite_name,
                    metrics.total_tests,
                    metrics.passed_tests,
                    metrics.failed_tests,
                    metrics.skipped_tests,
                    metrics.total_duration,
                    metrics.avg_execution_time,
                    metrics.success_rate,
                    metrics.timestamp,
                    metrics.coverage_percent,
                ),
            )
            conn.commit()

    def get_suite_history(self, suite_name: str, days: int = 30) -> List[SuiteMetrics]:
        """
        Retrieve historical suite metrics for trend analysis.

        Fetches suite execution records from the specified time window,
        ordered by most recent first. Used for generating historical
        reports and analyzing performance trends over time.

        Args:
            suite_name: Name of the test suite to retrieve history for
            days: Number of days of history to retrieve (default: 30)

        Returns:
            List of SuiteMetrics objects ordered by timestamp descending
            (most recent first). Returns empty list if no data found.

        Note:
            The ID column from the database is excluded from returned objects.
        """
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM suite_metrics
                WHERE suite_name = ? AND timestamp >= ?
                ORDER BY timestamp DESC
            """,
                (suite_name, cutoff_date),
            )

            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]

            return [
                SuiteMetrics(**dict(zip(columns[1:], row[1:]))) for row in rows  # Skip ID column
            ]

    def get_performance_trends(self, suite_name: str, days: int = 30) -> Dict[str, TrendData]:
        """
        Analyze performance trends for a test suite over time.

        Calculates trend direction and magnitude for key metrics:
        - Execution time (avg_execution_time)
        - Success rate
        - Code coverage (if available)

        Args:
            suite_name: Name of the test suite to analyze
            days: Number of days of history to analyze (default: 30)

        Returns:
            Dictionary mapping metric names to TrendData objects.
            Keys: 'execution_time', 'success_rate', 'coverage' (if available)
            Returns empty dict if insufficient data (less than 2 data points).

        Example:
            >>> trends = collector.get_performance_trends("auth_tests", days=7)
            >>> exec_trend = trends['execution_time']
            >>> print(f"Execution time is {exec_trend.trend_direction}")
        """
        history = self.get_suite_history(suite_name, days)

        if len(history) < 2:
            return {}  # Need at least 2 data points for trend analysis

        # Sort by timestamp chronologically for trend calculation
        history.sort(key=lambda x: x.timestamp)

        trends = {}

        # Analyze execution time trend
        execution_times = [h.avg_execution_time for h in history]
        timestamps = [h.timestamp for h in history]

        trends["execution_time"] = self._calculate_trend(
            "avg_execution_time", timestamps, execution_times
        )

        # Analyze success rate trend
        success_rates = [h.success_rate for h in history]
        trends["success_rate"] = self._calculate_trend("success_rate", timestamps, success_rates)

        # Analyze coverage trend (if data available)
        coverage_values = [h.coverage_percent for h in history if h.coverage_percent is not None]
        if coverage_values:
            coverage_timestamps = [h.timestamp for h in history if h.coverage_percent is not None]
            trends["coverage"] = self._calculate_trend(
                "coverage", coverage_timestamps, coverage_values
            )

        return trends

    def _calculate_trend(
        self, metric_name: str, timestamps: List[str], values: List[float]
    ) -> TrendData:
        """
        Calculate trend direction and percentage change for a metric.

        Uses a simple linear trend calculation by comparing the average
        of the first half of data points to the average of the second half.
        Trend direction interpretation depends on the metric type.

        Args:
            metric_name: Name of metric being analyzed
            timestamps: List of ISO timestamps for each value
            values: List of metric values to analyze

        Returns:
            TrendData object containing trend analysis results

        Trend Direction Logic:
            - Stable: Change magnitude < 5%
            - For success_rate and coverage metrics:
                - Positive change = "improving"
                - Negative change = "degrading"
            - For execution_time and other performance metrics:
                - Positive change = "degrading" (slower is worse)
                - Negative change = "improving" (faster is better)

        Note:
            Returns "stable" with 0% change if less than 2 data points provided.
        """
        if len(values) < 2:
            return TrendData(metric_name, timestamps, values, "stable", 0.0)

        # Split data in half and compare averages for simple linear trend
        first_half = values[: len(values) // 2]
        second_half = values[len(values) // 2 :]

        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)

        # Calculate percentage change (avoid division by zero)
        change_percent = ((second_avg - first_avg) / first_avg) * 100 if first_avg != 0 else 0

        # Determine trend direction based on metric type and change magnitude
        if abs(change_percent) < 5:  # Less than 5% change considered stable
            trend_direction = "stable"
        elif change_percent > 0:
            # For success rate and coverage, increase is good (improving)
            # For execution time, increase is bad (degrading - tests getting slower)
            if metric_name in ["success_rate", "coverage"]:
                trend_direction = "improving"
            else:
                trend_direction = "degrading"
        else:
            # Negative change
            if metric_name in ["success_rate", "coverage"]:
                trend_direction = "degrading"
            else:
                trend_direction = "improving"  # Execution time decrease is good

        return TrendData(metric_name, timestamps, values, trend_direction, change_percent)


class ReportGenerator:
    """
    Generates test execution reports in multiple formats.

    Creates comprehensive test reports from collected metrics data,
    supporting HTML, JSON, and Markdown output formats. Reports can
    cover individual test suites or provide an overview of all suites.

    The report generator integrates with TestMetricsCollector to retrieve
    historical data and trend analysis, producing formatted reports suitable
    for different audiences and use cases.

    Attributes:
        metrics_collector: TestMetricsCollector instance for data access
        logger: Logger instance for this class

    Example:
        >>> collector = TestMetricsCollector(Path("metrics.db"))
        >>> generator = ReportGenerator(collector)
        >>> generator.generate_html_report(Path("report.html"), "auth_tests")
        >>> generator.generate_json_report(Path("report.json"))
    """

    def __init__(self, metrics_collector: TestMetricsCollector):
        """
        Initialize report generator with metrics collector.

        Args:
            metrics_collector: TestMetricsCollector instance to retrieve
                metrics data from
        """
        self.metrics_collector = metrics_collector
        self.logger = logging.getLogger(__name__)

    def generate_html_report(self, output_path: Path, suite_name: Optional[str] = None):
        """
        Generate an HTML report with charts and metrics visualization.

        Creates a styled HTML report suitable for viewing in web browsers,
        including metric cards, trend indicators, and placeholder sections
        for future chart integration (e.g., Chart.js).

        Args:
            output_path: Path where HTML report will be saved
            suite_name: Optional suite name for single-suite report.
                If None, generates overview report for all suites.

        Note:
            - Single-suite reports include 30-day trend analysis
            - Overview reports show summary across all suites
            - HTML includes inline CSS styling for standalone viewing
        """
        html_content = self._build_html_report(suite_name)

        with open(output_path, "w") as f:
            f.write(html_content)

        self.logger.info(f"HTML report generated: {output_path}")

    def generate_json_report(self, output_path: Path, suite_name: Optional[str] = None) -> Dict:
        """
        Generate a JSON report for programmatic consumption.

        Creates a structured JSON report suitable for API integration,
        dashboards, or further processing by other tools.

        Args:
            output_path: Path where JSON report will be saved
            suite_name: Optional suite name for single-suite report.
                If None, generates overview report for all suites.

        Returns:
            Dictionary containing the report data that was written to file

        Note:
            - JSON is formatted with 2-space indentation for readability
            - Single-suite reports include full 30-day history and trends
            - Overview reports include last 7 days for all suites
        """
        report_data = self._build_report_data(suite_name)

        with open(output_path, "w") as f:
            json.dump(report_data, f, indent=2)

        self.logger.info(f"JSON report generated: {output_path}")
        return report_data

    def generate_markdown_report(self, output_path: Path, suite_name: Optional[str] = None):
        """
        Generate a Markdown report for documentation and README files.

        Creates a formatted Markdown report suitable for version control,
        GitHub/GitLab READMEs, or documentation sites. Includes emoji
        indicators for visual scanning.

        Args:
            output_path: Path where Markdown report will be saved
            suite_name: Optional suite name for single-suite report.
                If None, generates overview report for all suites.

        Note:
            - Uses emoji indicators (✅, ❌, ⚠️) for quick status visibility
            - Includes tables for suite overviews
            - Adds actionable recommendations based on metrics
        """
        markdown_content = self._build_markdown_report(suite_name)

        with open(output_path, "w") as f:
            f.write(markdown_content)

        self.logger.info(f"Markdown report generated: {output_path}")

    def _build_report_data(self, suite_name: Optional[str] = None) -> Dict:
        """Build report data structure."""
        if suite_name:
            # Single suite report
            history = self.metrics_collector.get_suite_history(suite_name, days=30)
            trends = self.metrics_collector.get_performance_trends(suite_name, days=30)

            return {
                "suite_name": suite_name,
                "generated_at": datetime.now().isoformat(),
                "history": [asdict(h) for h in history],
                "trends": {k: asdict(v) for k, v in trends.items()},
                "latest_metrics": asdict(history[0]) if history else None,
            }
        else:
            # All suites report
            with sqlite3.connect(self.metrics_collector.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT DISTINCT suite_name FROM suite_metrics
                    ORDER BY suite_name
                """
                )
                suite_names = [row[0] for row in cursor.fetchall()]

            suites_data = {}
            for name in suite_names:
                history = self.metrics_collector.get_suite_history(name, days=7)  # Last week
                trends = self.metrics_collector.get_performance_trends(name, days=7)

                suites_data[name] = {
                    "latest_metrics": asdict(history[0]) if history else None,
                    "trend_summary": self._summarize_trends(trends),
                }

            return {
                "generated_at": datetime.now().isoformat(),
                "suites": suites_data,
                "summary": self._calculate_overall_summary(suites_data),
            }

    def _build_html_report(self, suite_name: Optional[str] = None) -> str:
        """Build HTML report content."""
        report_data = self._build_report_data(suite_name)

        html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>E2E Test Report - {title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1, h2, h3 {{ color: #333; }}
        .metric-card {{ background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #007bff; }}
        .success {{ border-color: #28a745; }}
        .warning {{ border-color: #ffc107; }}
        .danger {{ border-color: #dc3545; }}
        .trend-up {{ color: #28a745; }}
        .trend-down {{ color: #dc3545; }}
        .trend-stable {{ color: #6c757d; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #f8f9fa; }}
        .chart-placeholder {{ background: #e9ecef; padding: 40px; text-align: center; margin: 20px 0; border-radius: 5px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>E2E Test Report</h1>
        <p><strong>Generated:</strong> {generated_at}</p>
        
        {content}
    </div>
</body>
</html>
        """

        if suite_name:
            content = self._build_suite_html_content(report_data)
            title = f"{suite_name} Suite"
        else:
            content = self._build_overview_html_content(report_data)
            title = "Overview"

        return html_template.format(
            title=title, generated_at=report_data["generated_at"], content=content
        )

    def _build_suite_html_content(self, data: Dict) -> str:
        """Build HTML content for single suite report."""
        latest = data.get("latest_metrics")
        if not latest:
            return "<p>No metrics available for this suite.</p>"

        trends_html = ""
        for trend_name, trend_data in data.get("trends", {}).items():
            direction_class = f"trend-{trend_data['trend_direction'].replace('degrading', 'down').replace('improving', 'up')}"
            trends_html += f"""
            <div class="metric-card">
                <h4>{trend_name.replace("_", " ").title()}</h4>
                <p class="{direction_class}">
                    {trend_data["trend_direction"].title()} 
                    ({trend_data["change_percent"]:+.1f}%)
                </p>
            </div>
            """

        return f"""
        <h2>Latest Metrics</h2>
        <div class="metric-card {"success" if latest["success_rate"] > 90 else "warning" if latest["success_rate"] > 70 else "danger"}">
            <h3>Success Rate: {latest["success_rate"]:.1f}%</h3>
            <p>Passed: {latest["passed_tests"]}, Failed: {latest["failed_tests"]}, Skipped: {latest["skipped_tests"]}</p>
        </div>
        
        <div class="metric-card">
            <h3>Performance</h3>
            <p>Average Execution Time: {latest["avg_execution_time"]:.2f}s</p>
            <p>Total Duration: {latest["total_duration"]:.2f}s</p>
        </div>
        
        <h2>Trends (Last 30 Days)</h2>
        {trends_html}
        
        <div class="chart-placeholder">
            Performance Charts Would Appear Here
            <br><small>(Chart.js integration would be added for production)</small>
        </div>
        """

    def _build_overview_html_content(self, data: Dict) -> str:
        """Build HTML content for overview report."""
        suites_html = ""

        for suite_name, suite_data in data.get("suites", {}).items():
            latest = suite_data.get("latest_metrics")
            if not latest:
                continue

            status_class = (
                "success"
                if latest["success_rate"] > 90
                else "warning" if latest["success_rate"] > 70 else "danger"
            )

            suites_html += f"""
            <tr>
                <td>{suite_name}</td>
                <td class="{status_class}">{latest["success_rate"]:.1f}%</td>
                <td>{latest["total_tests"]}</td>
                <td>{latest["avg_execution_time"]:.2f}s</td>
                <td>{latest["timestamp"][:10]}</td>
            </tr>
            """

        return f"""
        <h2>Test Suites Overview</h2>
        <table>
            <thead>
                <tr>
                    <th>Suite Name</th>
                    <th>Success Rate</th>
                    <th>Total Tests</th>
                    <th>Avg Duration</th>
                    <th>Last Run</th>
                </tr>
            </thead>
            <tbody>
                {suites_html}
            </tbody>
        </table>
        
        <h2>Summary</h2>
        {self._build_summary_html(data.get("summary", {}))}
        """

    def _build_summary_html(self, summary: Dict) -> str:
        """Build summary HTML section."""
        if not summary:
            return "<p>No summary data available.</p>"

        return f"""
        <div class="metric-card">
            <h3>Overall Health</h3>
            <p>Average Success Rate: {summary.get("avg_success_rate", 0):.1f}%</p>
            <p>Total Test Suites: {summary.get("total_suites", 0)}</p>
            <p>Suites Passing: {summary.get("passing_suites", 0)}</p>
        </div>
        """

    def _build_markdown_report(self, suite_name: Optional[str] = None) -> str:
        """Build Markdown report content."""
        report_data = self._build_report_data(suite_name)

        if suite_name:
            return self._build_suite_markdown_content(report_data)
        else:
            return self._build_overview_markdown_content(report_data)

    def _build_suite_markdown_content(self, data: Dict) -> str:
        """Build Markdown content for single suite report."""
        latest = data.get("latest_metrics")
        if not latest:
            return "# No Metrics Available\n\nNo metrics data found for this suite.\n"

        trends_md = ""
        for trend_name, trend_data in data.get("trends", {}).items():
            direction_emoji = (
                "📈"
                if trend_data["trend_direction"] == "improving"
                else "📉" if trend_data["trend_direction"] == "degrading" else "📊"
            )
            trends_md += f"- **{trend_name.replace('_', ' ').title()}**: {direction_emoji} {trend_data['trend_direction'].title()} ({trend_data['change_percent']:+.1f}%)\n"

        return f"""# E2E Test Report - {data["suite_name"]}

**Generated:** {data["generated_at"]}

## Latest Metrics

### Success Rate: {latest["success_rate"]:.1f}%
- ✅ Passed: {latest["passed_tests"]}
- ❌ Failed: {latest["failed_tests"]}
- ⏭️ Skipped: {latest["skipped_tests"]}

### Performance
- **Average Execution Time:** {latest["avg_execution_time"]:.2f}s
- **Total Duration:** {latest["total_duration"]:.2f}s
- **Last Run:** {latest["timestamp"]}

## Trends (Last 30 Days)

{trends_md}

## Recommendations

{self._generate_recommendations(latest, data.get("trends", {}))}
"""

    def _build_overview_markdown_content(self, data: Dict) -> str:
        """Build Markdown content for overview report."""
        suites_table = "| Suite Name | Success Rate | Total Tests | Avg Duration | Last Run |\n|------------|--------------|-------------|--------------|----------|\n"

        for suite_name, suite_data in data.get("suites", {}).items():
            latest = suite_data.get("latest_metrics")
            if not latest:
                continue

            status_emoji = (
                "✅"
                if latest["success_rate"] > 90
                else "⚠️" if latest["success_rate"] > 70 else "❌"
            )

            suites_table += f"| {suite_name} | {status_emoji} {latest['success_rate']:.1f}% | {latest['total_tests']} | {latest['avg_execution_time']:.2f}s | {latest['timestamp'][:10]} |\n"

        summary = data.get("summary", {})

        return f"""# E2E Test Report - Overview

**Generated:** {data["generated_at"]}

## Test Suites Status

{suites_table}

## Summary

- **Total Test Suites:** {summary.get("total_suites", 0)}
- **Suites Passing (>90%):** {summary.get("passing_suites", 0)}
- **Average Success Rate:** {summary.get("avg_success_rate", 0):.1f}%

## Overall Health: {self._get_health_status(summary)}

{self._generate_overview_recommendations(data.get("suites", {}))}
"""

    def _summarize_trends(self, trends: Dict[str, TrendData]) -> Dict:
        """Summarize trend data for overview."""
        summary = {}
        for trend_name, trend_data in trends.items():
            summary[trend_name] = {
                "direction": trend_data.trend_direction,
                "change_percent": trend_data.change_percent,
            }
        return summary

    def _calculate_overall_summary(self, suites_data: Dict) -> Dict:
        """Calculate overall summary statistics."""
        total_suites = len(suites_data)
        passing_suites = 0
        success_rates = []

        for suite_data in suites_data.values():
            latest = suite_data.get("latest_metrics")
            if latest:
                success_rates.append(latest["success_rate"])
                if latest["success_rate"] > 90:
                    passing_suites += 1

        avg_success_rate = sum(success_rates) / len(success_rates) if success_rates else 0

        return {
            "total_suites": total_suites,
            "passing_suites": passing_suites,
            "avg_success_rate": avg_success_rate,
        }

    def _generate_recommendations(self, latest_metrics: Dict, trends: Dict) -> str:
        """Generate recommendations based on metrics and trends."""
        recommendations = []

        # Success rate recommendations
        if latest_metrics["success_rate"] < 90:
            recommendations.append(
                "🚨 Success rate is below 90%. Investigate and fix failing tests."
            )

        # Performance recommendations
        execution_trend = trends.get("execution_time")
        if execution_trend and execution_trend["trend_direction"] == "degrading":
            recommendations.append(
                "⚠️ Execution time is increasing. Consider performance optimization."
            )

        # Coverage recommendations
        if latest_metrics.get("coverage_percent") and latest_metrics["coverage_percent"] < 80:
            recommendations.append("📝 Code coverage is below 80%. Add more comprehensive tests.")

        if not recommendations:
            recommendations.append("✅ All metrics look good! Keep up the excellent work.")

        return "\n".join(f"- {rec}" for rec in recommendations)

    def _generate_overview_recommendations(self, suites_data: Dict) -> str:
        """Generate overview recommendations."""
        failing_suites = []

        for suite_name, suite_data in suites_data.items():
            latest = suite_data.get("latest_metrics")
            if latest and latest["success_rate"] < 80:
                failing_suites.append(suite_name)

        recommendations = []

        if failing_suites:
            recommendations.append(
                f"🚨 **Critical:** The following suites need immediate attention: {', '.join(failing_suites)}"
            )

        recommendations.append(
            "📊 Regular monitoring helps maintain test quality and catch regressions early."
        )
        recommendations.append(
            "🔄 Consider setting up automated alerts for significant metric changes."
        )

        return "## Recommendations\n\n" + "\n".join(f"- {rec}" for rec in recommendations)

    def _get_health_status(self, summary: Dict) -> str:
        """Get overall health status."""
        avg_success_rate = summary.get("avg_success_rate", 0)

        if avg_success_rate >= 95:
            return "🟢 Excellent"
        elif avg_success_rate >= 85:
            return "🟡 Good"
        elif avg_success_rate >= 70:
            return "🟠 Needs Attention"
        else:
            return "🔴 Critical"


class AlertSystem:
    """
    Automated alert system for test failures and performance degradation.

    Monitors test metrics against predefined thresholds and triggers alerts
    when critical conditions are detected. Provides integration points for
    various notification channels (Slack, email, PagerDuty, etc.).

    Alert Thresholds:
        Success Rate:
            - Critical: < 80%
            - Warning: < 95%
        Performance Degradation:
            - Warning: Execution time increased > 20% over 7 days

    Attributes:
        metrics_collector: TestMetricsCollector for retrieving trend data
        logger: Logger instance for this class

    Example:
        >>> collector = TestMetricsCollector(Path("metrics.db"))
        >>> alert_system = AlertSystem(collector)
        >>> suite_metrics = SuiteMetrics(...)
        >>> alert_system.check_and_send_alerts("auth_tests", suite_metrics)
    """

    def __init__(self, metrics_collector: TestMetricsCollector):
        """
        Initialize alert system with metrics collector.

        Args:
            metrics_collector: TestMetricsCollector instance for accessing
                historical metrics and trend data
        """
        self.metrics_collector = metrics_collector
        self.logger = logging.getLogger(__name__)

    def check_and_send_alerts(self, suite_name: str, latest_metrics: SuiteMetrics):
        """
        Check metrics against thresholds and send alerts if exceeded.

        Evaluates the latest suite metrics and recent trends to identify
        conditions requiring notification. Multiple alerts may be generated
        if multiple thresholds are exceeded.

        Args:
            suite_name: Name of the test suite being checked
            latest_metrics: Most recent SuiteMetrics for this suite

        Alert Conditions:
            1. Success rate < 80% → Critical alert
            2. Success rate < 95% → Warning alert
            3. Execution time increase > 20% over 7 days → Warning alert

        Note:
            Currently logs alerts. Extend _send_alert() for actual notifications.
        """
        alerts = []

        # Success rate threshold checks
        if latest_metrics.success_rate < 80:
            alerts.append(
                {
                    "level": "critical",
                    "message": f"Success rate dropped to {latest_metrics.success_rate:.1f}% in {suite_name}",
                }
            )
        elif latest_metrics.success_rate < 95:
            alerts.append(
                {
                    "level": "warning",
                    "message": f"Success rate is {latest_metrics.success_rate:.1f}% in {suite_name}",
                }
            )

        # Performance degradation check (7-day trend)
        trends = self.metrics_collector.get_performance_trends(suite_name, days=7)
        execution_trend = trends.get("execution_time")

        if (
            execution_trend
            and execution_trend.trend_direction == "degrading"
            and execution_trend.change_percent > 20
        ):
            alerts.append(
                {
                    "level": "warning",
                    "message": f"Execution time increased by {execution_trend.change_percent:.1f}% in {suite_name}",
                }
            )

        # Send all triggered alerts
        for alert in alerts:
            self._send_alert(alert)

    def _send_alert(self, alert: Dict):
        """
        Send alert notification through configured channels.

        Currently logs alerts to the application logger. This method serves
        as an integration point for external notification systems.

        Args:
            alert: Dictionary with 'level' (critical/warning) and 'message' keys

        Integration Points:
            To add notification channels, extend this method with:
            - Slack webhooks (slack_sdk)
            - Email (SMTP)
            - PagerDuty API
            - Discord webhooks
            - Microsoft Teams
            - Custom monitoring systems

        Example Integration:
            >>> # Add to this method:
            >>> import requests
            >>> if alert['level'] == 'critical':
            >>>     requests.post(SLACK_WEBHOOK_URL, json={'text': alert['message']})
        """
        self.logger.warning(f"ALERT [{alert['level'].upper()}]: {alert['message']}")

        # TODO: Add integrations here:
        # - Slack notifications
        # - Email alerts
        # - PagerDuty
        # - Discord webhooks
        # - Custom webhook endpoints


# Example usage and integration function
def monitor_test_execution(test_results: Dict, output_dir: Path):
    """
    Monitor test execution and generate comprehensive reports.

    This is a convenience function demonstrating the complete workflow
    for integrating the monitoring system into a test suite. It handles
    metrics collection, alert checking, and multi-format report generation.

    Args:
        test_results: Dictionary mapping suite names to result dictionaries.
            Each result dict should contain:
                - 'total': Total number of tests (int)
                - 'passed': Number of passed tests (int)
                - 'failed': Number of failed tests (int)
                - 'skipped': Number of skipped tests (int)
                - 'duration': Total execution time in seconds (float)
                - 'avg_time': Average test execution time (float)
                - 'success_rate': Success rate percentage (float)
                - 'coverage': Optional code coverage percentage (float)

        output_dir: Directory path where reports and database will be saved

    Returns:
        Tuple of (metrics_collector, report_generator) for further use

    Example:
        >>> test_results = {
        ...     'auth_tests': {
        ...         'total': 10, 'passed': 9, 'failed': 1, 'skipped': 0,
        ...         'duration': 15.3, 'avg_time': 1.53, 'success_rate': 90.0
        ...     },
        ...     'api_tests': {
        ...         'total': 25, 'passed': 25, 'failed': 0, 'skipped': 0,
        ...         'duration': 42.7, 'avg_time': 1.71, 'success_rate': 100.0
        ...     }
        ... }
        >>> collector, generator = monitor_test_execution(
        ...     test_results, Path("./test_output")
        ... )

    Side Effects:
        - Creates SQLite database at output_dir/test_metrics.db
        - Generates test_report.html in output_dir
        - Generates test_report.json in output_dir
        - Generates test_report.md in output_dir
        - Logs alerts if thresholds exceeded
    """
    # Initialize monitoring components
    metrics_collector = TestMetricsCollector(output_dir / "test_metrics.db")
    report_generator = ReportGenerator(metrics_collector)
    alert_system = AlertSystem(metrics_collector)

    # Process each test suite
    for suite_name, suite_result in test_results.items():
        # Convert test framework results to metrics format
        suite_metrics = SuiteMetrics(
            suite_name=suite_name,
            total_tests=suite_result.get("total", 0),
            passed_tests=suite_result.get("passed", 0),
            failed_tests=suite_result.get("failed", 0),
            skipped_tests=suite_result.get("skipped", 0),
            total_duration=suite_result.get("duration", 0),
            avg_execution_time=suite_result.get("avg_time", 0),
            success_rate=suite_result.get("success_rate", 0),
            timestamp=datetime.now().isoformat(),
            coverage_percent=suite_result.get("coverage", None),
        )

        # Persist metrics to database
        metrics_collector.record_suite_metrics(suite_metrics)

        # Check for alert conditions and notify if needed
        alert_system.check_and_send_alerts(suite_name, suite_metrics)

    # Generate all report formats
    report_generator.generate_html_report(output_dir / "test_report.html")
    report_generator.generate_json_report(output_dir / "test_report.json")
    report_generator.generate_markdown_report(output_dir / "test_report.md")

    return metrics_collector, report_generator
