#!/usr/bin/env python3
"""Security check script to validate critical fixes have been applied.

This script performs comprehensive security audits on the codebase to identify
potential vulnerabilities before production deployment. It runs both static
analysis checks and integrates with external security tools.

Security Checks Performed:
    - SQL injection vulnerabilities
    - Unsafe pickle deserialization
    - Subprocess shell injection risks
    - Hardcoded secrets and credentials
    - Poor exception handling patterns
    - Resource cleanup issues

External Tools Integration:
    - Bandit: Python security linter
    - Safety: Dependency vulnerability scanner

Usage:
    python scripts/security_check.py

Exit Codes:
    0: All security checks passed
    1: Security issues found, deployment blocked
"""

import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# ANSI color codes for terminal output
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


class SecurityChecker:
    """Automated security vulnerability scanner for Python codebases.

    Performs static analysis to identify common security issues including
    SQL injection, unsafe deserialization, shell injection, hardcoded secrets,
    poor error handling, and resource leaks.

    Attributes:
        project_root: Root directory of the project to scan
        src_dir: Source code directory (project_root/src)
        issues: List of critical security issues found
        warnings: List of non-critical security warnings

    Example:
        >>> checker = SecurityChecker(Path('/path/to/project'))
        >>> passed, issues, warnings = checker.run_all_checks()
        >>> if not passed:
        ...     print(f"Found {len(issues)} critical issues")
    """

    def __init__(self, project_root: Path):
        """Initialize the security checker.

        Args:
            project_root: Path to the project root directory
        """
        self.project_root = project_root
        self.src_dir = project_root / "src"
        self.issues: List[Dict] = []
        self.warnings: List[Dict] = []

    def run_all_checks(self) -> Tuple[bool, List[Dict], List[Dict]]:
        """Execute all security checks on the codebase.

        Runs comprehensive security analysis including SQL injection detection,
        unsafe pickle usage, subprocess vulnerabilities, hardcoded secrets,
        exception handling issues, and resource cleanup problems.

        Returns:
            Tuple containing:
                - all_passed (bool): True if no critical issues found
                - critical_issues (List[Dict]): List of critical security issues
                - warnings (List[Dict]): List of non-critical warnings
        """
        print(f"{BLUE}Starting Security Audit...{RESET}\n")

        # Run checks
        self.check_sql_injection()
        self.check_pickle_usage()
        self.check_subprocess_shell()
        self.check_hardcoded_secrets()
        self.check_exception_handling()
        self.check_resource_cleanup()

        # Summary
        all_passed = len(self.issues) == 0
        return all_passed, self.issues, self.warnings

    def check_sql_injection(self) -> None:
        """Detect potential SQL injection vulnerabilities.

        Scans for unsafe SQL query construction patterns including:
        - f-strings in SQL queries
        - Percent (%) formatting in SQL
        - String .format() in SQL
        - String concatenation in SQL WHERE clauses

        These patterns indicate user input may be directly interpolated
        into SQL queries without proper parameterization.
        """
        print("Checking for SQL injection vulnerabilities...")

        # Regex patterns detecting unsafe SQL construction methods
        # These patterns look for dynamic SQL with user input interpolation
        sql_patterns = [
            r'f".*SELECT.*WHERE.*{',  # f-string in SQL (e.g., f"SELECT * WHERE id={user_id}")
            r"f'.*SELECT.*WHERE.*{",  # f-string in SQL with single quotes
            r"%.*SELECT.*WHERE.*%",  # % formatting in SQL (e.g., "SELECT * WHERE id=%s" % user_id)
            r"\.format\(.*SELECT.*WHERE",  # .format() in SQL (e.g., "SELECT * WHERE id={}".format(user_id))
            r"\+.*SELECT.*WHERE.*\+",  # String concatenation in SQL (e.g., "SELECT * WHERE id=" + user_id)
        ]

        # Scan all Python files in the source directory
        for py_file in self.src_dir.rglob("*.py"):
            content = py_file.read_text()
            for pattern in sql_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    self.issues.append(
                        {
                            "type": "SQL_INJECTION",
                            "file": str(py_file.relative_to(self.project_root)),
                            "severity": "CRITICAL",
                            "message": "Potential SQL injection vulnerability",
                        }
                    )
                    break  # One issue per file is sufficient

        self._print_check_result("SQL Injection", "SQL_INJECTION")

    def check_pickle_usage(self) -> None:
        """Detect unsafe pickle/dill deserialization patterns.

        Identifies use of pickle.load/loads, cPickle, and dill deserialization
        without proper validation. Deserializing untrusted data can lead to
        arbitrary code execution vulnerabilities.

        The check looks for validation patterns (hmac, signature verification,
        trusted source checks) in surrounding code. If no validation is found,
        a critical issue is reported.
        """
        print("Checking for unsafe pickle usage...")

        pickle_patterns = [
            r"pickle\.loads?\(",
            r"pickle\.load\(",
            r"cPickle\.loads?\(",
            r"dill\.loads?\(",
        ]

        for py_file in self.src_dir.rglob("*.py"):
            content = py_file.read_text()
            for pattern in pickle_patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    # Calculate line number by counting newlines before the match
                    line_num = content[: match.start()].count("\n") + 1
                    # Check if pickle usage has security validation in surrounding code
                    if not self._is_pickle_safe(py_file, line_num):
                        self.issues.append(
                            {
                                "type": "UNSAFE_PICKLE",
                                "file": str(py_file.relative_to(self.project_root)),
                                "line": line_num,
                                "severity": "CRITICAL",
                                "message": "Unsafe pickle deserialization",
                            }
                        )

        self._print_check_result("Pickle Usage", "UNSAFE_PICKLE")

    def check_subprocess_shell(self) -> None:
        """Detect shell injection vulnerabilities in subprocess calls.

        Identifies dangerous patterns:
        - subprocess calls with shell=True (enables shell injection)
        - os.system() usage (deprecated and unsafe)

        shell=True allows shell metacharacters in commands, creating
        injection risks if user input is included. Use subprocess with
        shell=False and pass commands as lists instead.
        """
        print("Checking for unsafe subprocess calls...")

        for py_file in self.src_dir.rglob("*.py"):
            content = py_file.read_text()

            # Check for shell=True parameter which enables shell injection
            if "shell=True" in content:
                lines = content.split("\n")
                for i, line in enumerate(lines, 1):
                    if "shell=True" in line:
                        self.issues.append(
                            {
                                "type": "SHELL_INJECTION",
                                "file": str(py_file.relative_to(self.project_root)),
                                "line": i,
                                "severity": "HIGH",
                                "message": "subprocess with shell=True is dangerous",
                            }
                        )

            # Check for deprecated os.system() which always uses shell
            if "os.system(" in content:
                self.issues.append(
                    {
                        "type": "SHELL_INJECTION",
                        "file": str(py_file.relative_to(self.project_root)),
                        "severity": "HIGH",
                        "message": "os.system() is dangerous, use subprocess",
                    }
                )

        self._print_check_result("Subprocess Security", "SHELL_INJECTION")

    def check_hardcoded_secrets(self) -> None:
        """Detect hardcoded secrets and API keys in source code.

        Scans for common patterns indicating hardcoded credentials:
        - api_key, password, secret, token variable assignments
        - API key patterns (e.g., 'sk-...', 'AIza...')

        Filters out placeholders and references to environment variables
        to reduce false positives. Secrets should be loaded from environment
        variables or secure credential stores, never committed to source.
        """
        print("Checking for hardcoded secrets...")

        secret_patterns = [
            r'api_key\s*=\s*["\'][^"\']+["\']',
            r'password\s*=\s*["\'][^"\']+["\']',
            r'secret\s*=\s*["\'][^"\']+["\']',
            r'token\s*=\s*["\'][^"\']+["\']',
            r'["\']sk-[a-zA-Z0-9]{40,}["\']',  # API keys
            r'["\']AIza[a-zA-Z0-9_-]{35}["\']',  # Google API keys
        ]

        for py_file in self.src_dir.rglob("*.py"):
            content = py_file.read_text()
            for pattern in secret_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    # Filter out common placeholders and environment variable references
                    # to reduce false positives from example code or proper secret management
                    if not any(
                        placeholder in content
                        for placeholder in [
                            "your-api-key",
                            "your_api_key",
                            "<api_key>",
                            "example",
                            "placeholder",
                            "getenv",
                            "environ",
                        ]
                    ):
                        self.warnings.append(
                            {
                                "type": "HARDCODED_SECRET",
                                "file": str(py_file.relative_to(self.project_root)),
                                "severity": "HIGH",
                                "message": "Possible hardcoded secret",
                            }
                        )

        self._print_check_result("Hardcoded Secrets", "HARDCODED_SECRET", check_warnings=True)

    def check_exception_handling(self) -> None:
        """Identify poor exception handling patterns.

        Detects problematic error handling:
        - Bare except clauses (catches all exceptions including system exits)
        - Overly broad except Exception
        - Silent failures (except: pass)

        These patterns can hide bugs, make debugging difficult, and may
        catch critical system exceptions that should propagate.
        """
        print("Checking exception handling...")

        bad_patterns = [
            r"except\s*:",  # Bare except
            r"except\s+Exception\s*:",  # Too broad
            r"except.*:\s*pass",  # Silent failure
        ]

        for py_file in self.src_dir.rglob("*.py"):
            content = py_file.read_text()
            for pattern in bad_patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    line_num = content[: match.start()].count("\n") + 1
                    self.warnings.append(
                        {
                            "type": "POOR_ERROR_HANDLING",
                            "file": str(py_file.relative_to(self.project_root)),
                            "line": line_num,
                            "severity": "MEDIUM",
                            "message": "Poor exception handling pattern",
                        }
                    )

        self._print_check_result("Exception Handling", "POOR_ERROR_HANDLING", check_warnings=True)

    def check_resource_cleanup(self) -> None:
        """Detect potential resource leaks from missing cleanup.

        Identifies files opened without context managers (with statements).
        Files opened without proper cleanup may remain open, causing:
        - File descriptor leaks
        - Data corruption from unflushed buffers
        - Permission lock issues on Windows

        Use 'with open(...)' instead of bare 'open()' assignments.
        """
        print("Checking resource cleanup...")

        for py_file in self.src_dir.rglob("*.py"):
            content = py_file.read_text()

            # Check for open() without context manager (missing 'with' statement)
            # Pattern matches: var = open(...) but not: with open(...) as var
            if re.search(r"=\s*open\([^)]+\)", content):
                lines = content.split("\n")
                for i, line in enumerate(lines, 1):
                    if re.search(r"=\s*open\([^)]+\)", line) and "with" not in line:
                        self.warnings.append(
                            {
                                "type": "RESOURCE_LEAK",
                                "file": str(py_file.relative_to(self.project_root)),
                                "line": i,
                                "severity": "MEDIUM",
                                "message": "File opened without context manager",
                            }
                        )

        self._print_check_result("Resource Cleanup", "RESOURCE_LEAK", check_warnings=True)

    def _is_pickle_safe(self, file_path: Path, line_num: int) -> bool:
        """Determine if pickle usage has proper security validation.

        Examines the context around pickle deserialization (±5 lines) to
        detect validation mechanisms such as:
        - HMAC signature verification
        - Digital signature checks
        - Explicit validation functions
        - Trusted source verification

        Args:
            file_path: Path to the Python file containing pickle usage
            line_num: Line number where pickle.load/loads is used

        Returns:
            True if validation is detected in surrounding context, False otherwise
        """
        content = file_path.read_text()
        lines = content.split("\n")

        # Examine a 10-line window (±5 lines) around the pickle usage
        # to look for security validation code
        start = max(0, line_num - 5)
        end = min(len(lines), line_num + 5)

        context = "\n".join(lines[start:end])

        # Look for keywords indicating security validation mechanisms
        # HMAC, signatures, or explicit validation functions suggest
        # the data source is authenticated/verified
        if any(
            check in context for check in ["hmac", "signature", "verify", "validate", "trusted"]
        ):
            return True

        return False

    def _print_check_result(
        self, check_name: str, issue_type: str, check_warnings: bool = False
    ) -> None:
        """Print formatted results for a security check.

        Displays colored output indicating pass/fail status and count
        of issues or warnings found.

        Args:
            check_name: Human-readable name of the check (unused, for clarity)
            issue_type: Type identifier to filter issues/warnings by
            check_warnings: If True, check warnings list; if False, check issues list
        """
        if check_warnings:
            count = len([w for w in self.warnings if w["type"] == issue_type])
            if count > 0:
                print(f"  {YELLOW}⚠ Found {count} warnings{RESET}")
            else:
                print(f"  {GREEN}✓ No issues found{RESET}")
        else:
            count = len([i for i in self.issues if i["type"] == issue_type])
            if count > 0:
                print(f"  {RED}✗ Found {count} vulnerabilities{RESET}")
            else:
                print(f"  {GREEN}✓ Secure{RESET}")


def run_external_tools() -> Dict[str, bool]:
    """Execute external security scanning tools.

    Attempts to run third-party security tools if installed:

    - Bandit: Static analysis security linter for Python code.
      Checks for common security issues with configurable severity levels.

    - Safety: Scans Python dependencies against a database of known
      security vulnerabilities. Checks requirements for CVEs.

    Each tool runs with a 30-second timeout. Missing tools are noted
    but don't fail the audit.

    Returns:
        Dictionary mapping tool names to their pass/fail status.
        Tools that aren't installed are excluded from results.
    """
    results = {}

    print(f"\n{BLUE}Running External Security Tools...{RESET}\n")

    # Run Bandit: Python security linter
    # Scans for common security issues like hardcoded passwords, SQL injection, etc.
    try:
        result = subprocess.run(
            ["bandit", "-r", "src/", "-f", "json"], capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            print(f"  {GREEN}✓ Bandit: No issues{RESET}")
            results["bandit"] = True
        else:
            print(f"  {YELLOW}⚠ Bandit: Found issues{RESET}")
            results["bandit"] = False
    except (subprocess.SubprocessError, FileNotFoundError):
        print(f"  {YELLOW}⚠ Bandit not installed{RESET}")

    # Run Safety: Dependency vulnerability scanner
    # Checks installed packages against a database of known CVEs
    try:
        result = subprocess.run(
            ["safety", "check", "--json"], capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            print(f"  {GREEN}✓ Safety: No vulnerable dependencies{RESET}")
            results["safety"] = True
        else:
            print(f"  {RED}✗ Safety: Vulnerable dependencies found{RESET}")
            results["safety"] = False
    except (subprocess.SubprocessError, FileNotFoundError):
        print(f"  {YELLOW}⚠ Safety not installed{RESET}")

    return results


def main():
    """Execute complete security audit and report results.

    Runs all internal security checks and external tool scans,
    then generates a comprehensive report with:
    - Critical issues (block deployment)
    - Warnings (should be reviewed)
    - External tool results
    - Final pass/fail verdict

    Exits with code 0 if all checks pass, 1 if issues are found.
    """
    print(f"\n{BLUE}═══════════════════════════════════════════{RESET}")
    print(f"{BLUE}   SECURITY AUDIT - Audio Extraction Project{RESET}")
    print(f"{BLUE}═══════════════════════════════════════════{RESET}\n")

    project_root = Path(__file__).parent.parent
    checker = SecurityChecker(project_root)

    # Run security checks
    all_passed, issues, warnings = checker.run_all_checks()

    # Run external tools
    external_results = run_external_tools()

    # Print summary
    print(f"\n{BLUE}═══════════════════════════════════════════{RESET}")
    print(f"{BLUE}                   SUMMARY{RESET}")
    print(f"{BLUE}═══════════════════════════════════════════{RESET}\n")

    if issues:
        print(f"{RED}CRITICAL ISSUES FOUND: {len(issues)}{RESET}\n")
        for issue in issues:
            print(f"  {RED}✗ [{issue['severity']}] {issue['type']}{RESET}")
            print(f"    File: {issue['file']}")
            if "line" in issue:
                print(f"    Line: {issue['line']}")
            print(f"    {issue['message']}\n")

    if warnings:
        print(f"{YELLOW}WARNINGS: {len(warnings)}{RESET}\n")
        for warning in warnings[:5]:  # Show first 5 warnings
            print(f"  {YELLOW}⚠ [{warning['severity']}] {warning['type']}{RESET}")
            print(f"    File: {warning['file']}")
            if "line" in warning:
                print(f"    Line: {warning['line']}")
            print(f"    {warning['message']}\n")

        if len(warnings) > 5:
            print(f"  {YELLOW}... and {len(warnings) - 5} more warnings{RESET}\n")

    # Final verdict
    print(f"{BLUE}═══════════════════════════════════════════{RESET}")
    if all_passed and all(external_results.values()):
        print(f"{GREEN}    ✅ SECURITY AUDIT PASSED{RESET}")
        print(f"{GREEN}    Ready for production deployment{RESET}")
        sys.exit(0)
    else:
        print(f"{RED}    ❌ SECURITY AUDIT FAILED{RESET}")
        print(f"{RED}    DO NOT DEPLOY TO PRODUCTION{RESET}")
        print(f"\n{YELLOW}Fix all critical issues before deployment.{RESET}")
        print(f"{YELLOW}See PRODUCTION_READINESS_REPORT.md for details.{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
