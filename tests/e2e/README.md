# End-to-End Testing Framework

This comprehensive E2E testing framework ensures the `audio-extraction-analysis` tool is production-ready through systematic validation of all components, integrations, and workflows.

## Overview

The E2E testing framework provides:

- **Complete CLI Testing**: Validates all command-line operations
- **Provider Integration Testing**: Tests all transcription providers and auto-selection
- **Performance Benchmarking**: Monitors execution time and resource usage
- **Security Validation**: Prevents vulnerabilities and ensures safe operation
- **Automated Reporting**: Generates detailed reports with trends and recommendations
- **CI/CD Integration**: Seamless GitHub Actions workflow

## Framework Structure

```
tests/e2e/
├── __init__.py                    # Framework initialization
├── base.py                        # Base test classes and utilities
├── test_data_manager.py           # Test media file generation
├── test_cli_integration.py        # CLI command integration tests
├── test_provider_integration.py   # Provider factory and integration tests
├── test_performance.py            # Performance and load testing
├── test_security.py               # Security vulnerability testing
├── monitoring.py                  # Metrics collection and reporting
├── run_e2e_tests.py              # Comprehensive test runner
└── test_data/                     # Generated test media files
```

## Quick Start

### Local Development

```bash
# Quick test (unit + integration)
./scripts/run_e2e_local.sh -q

# Run all E2E tests
./scripts/run_e2e_local.sh

# Run specific suite with coverage
./scripts/run_e2e_local.sh -s cli -c

# Performance tests with fresh data
./scripts/run_e2e_local.sh -s performance -g
```

### Using the Python Runner

```bash
# Run all tests with coverage
python tests/e2e/run_e2e_tests.py --suite all --coverage

# Run only CLI tests
python tests/e2e/run_e2e_tests.py --suite cli --verbose

# Generate fresh test data
python tests/e2e/run_e2e_tests.py --generate-test-data
```

## Test Suites

### 1. Unit Tests (`unit`)
- **Location**: `tests/unit/`
- **Purpose**: Component isolation testing
- **Duration**: < 30 seconds
- **Coverage**: Individual modules and functions

### 2. Integration Tests (`integration`)
- **Location**: `tests/integration/`
- **Purpose**: Service interaction validation
- **Duration**: < 2 minutes
- **Coverage**: Provider factory, CLI integration

### 3. CLI Integration Tests (`cli`)
- **Location**: `tests/e2e/test_cli_integration.py`
- **Purpose**: End-to-end CLI command validation
- **Duration**: < 15 minutes
- **Coverage**: Extract, transcribe, and process commands

### 4. Provider Integration Tests (`provider`)
- **Location**: `tests/e2e/test_provider_integration.py`
- **Purpose**: Transcription provider validation
- **Duration**: < 10 minutes
- **Coverage**: Factory pattern, auto-selection, fallback mechanisms

### 5. Performance Tests (`performance`)
- **Location**: `tests/e2e/test_performance.py`
- **Purpose**: Performance benchmarking and load testing
- **Duration**: < 30 minutes
- **Coverage**: Resource usage, concurrent operations, scalability

### 6. Security Tests (`security`)
- **Location**: `tests/e2e/test_security.py`
- **Purpose**: Security vulnerability validation
- **Duration**: < 5 minutes
- **Coverage**: Input validation, output sanitization, API key security

## Test Data Management

### Automatic Generation

The framework automatically generates test media files using FFmpeg:

```python
from tests.e2e.test_data_manager import TestDataManager

# Generate all test files
manager = TestDataManager()
files = manager.generate_all_test_files()

# Generate specific file
custom_file = manager.create_custom_test_file(
    name="custom_test.mp4",
    duration=30,
    video_size="1280x720"
)
```

### Available Test Files

| File Type | Duration | Size | Purpose |
|-----------|----------|------|---------|
| `test_short.mp4` | 5 seconds | ~1MB | Basic functionality |
| `test_medium.mp4` | 2 minutes | ~20MB | Standard workflow |
| `test_long.mp4` | 30 minutes | ~300MB | Performance testing |
| `test_audio.mp3` | 10 seconds | ~200KB | Audio-only pipeline |
| `test_corrupted.mp4` | N/A | 1KB | Error handling |
| `test_empty.mp4` | N/A | 0B | Edge case handling |
| `test_unicode_名前.mp4` | 5 seconds | ~1MB | Unicode support |

## Performance Benchmarks

### Target Metrics

| Operation | Input Size | Target Time | Memory Limit |
|-----------|------------|-------------|--------------|
| Extract (5s video) | ~1MB | < 30s | < 100MB |
| Extract (2min video) | ~20MB | < 60s | < 200MB |
| Transcribe (10s audio) | ~200KB | < 45s | < 150MB |
| Process (5s video) | ~1MB | < 90s | < 200MB |
| Process (2min video) | ~20MB | < 300s | < 500MB |

### Performance Monitoring

The framework tracks:
- Execution time per operation
- Peak memory usage
- CPU utilization
- Concurrent operation handling
- Memory leak detection

## Security Testing

### Validation Areas

1. **Input Validation**
   - Path traversal prevention
   - Command injection protection
   - Filename sanitization
   - Unicode handling

2. **Output Sanitization**
   - API key redaction
   - Content sanitization
   - File permission validation
   - Temporary file cleanup

3. **API Key Security**
   - Environment isolation
   - Key validation
   - Storage security
   - Exposure prevention

## Provider Testing

### Test Matrix

| Scenario | Deepgram | ElevenLabs | Expected Behavior |
|----------|----------|------------|-------------------|
| All configured | ✅ | ✅ | Auto-select best |
| Deepgram only | ✅ | ❌ | Use Deepgram |
| ElevenLabs only | ❌ | ✅ | Use ElevenLabs |
| None configured | ❌ | ❌ | Graceful error |
| Invalid keys | ❌ | ❌ | Fallback handling |

### Provider Features

The framework validates:
- Provider initialization
- Feature availability (diarization, sentiment analysis)
- File size limits
- Error handling and fallback
- Rate limiting responses

## Continuous Integration

### GitHub Actions Workflow

The CI pipeline includes:

1. **Environment Validation**
   - Python version check
   - Dependency installation
   - Tool availability

2. **Test Execution**
   - Unit tests with coverage
   - Integration tests
   - E2E test suites
   - Security validation

3. **Reporting**
   - Test result aggregation
   - Coverage reporting
   - Performance metrics
   - Security scan results

4. **Production Readiness**
   - Success rate assessment
   - Performance validation
   - Security compliance
   - Release gate decisions

### Workflow Triggers

- **Push/PR**: Core test suites
- **Nightly**: Extended performance tests
- **Manual**: Configurable test selection
- **Release**: Full validation suite

## Monitoring and Reporting

### Metrics Collection

The framework collects:
- Test execution metrics
- Performance benchmarks
- Success/failure rates
- Trend analysis data
- Coverage statistics

### Report Types

1. **HTML Reports**: Interactive dashboards with charts
2. **JSON Reports**: Machine-readable metrics data
3. **Markdown Reports**: Human-readable summaries
4. **Trend Analysis**: Historical performance tracking

### Alert System

Automated alerts for:
- Success rate drops below 80%
- Performance degradation > 20%
- Security test failures
- Critical dependency issues

## Configuration

### Environment Variables

```bash
# Required for real API testing
export DEEPGRAM_API_KEY="your_deepgram_key"
export ELEVENLABS_API_KEY="your_elevenlabs_key"

# Test configuration
export TEST_MODE="true"
export LOG_LEVEL="DEBUG"
export TEST_TIMEOUT="600"
```

### Test Runner Options

```bash
python tests/e2e/run_e2e_tests.py \
  --suite all \              # Test suite selection
  --coverage \               # Generate coverage reports
  --parallel \               # Parallel execution
  --fail-fast \              # Stop on first failure
  --verbose \                # Detailed output
  --generate-test-data \     # Fresh test data
  --real-api-keys \          # Use real APIs
  --keep-artifacts           # Preserve test files
```

## Best Practices

### Writing Tests

1. **Use Base Classes**: Inherit from `E2ETestBase` for utilities
2. **Mock External Services**: Use provided mixin classes
3. **Validate Thoroughly**: Check files, outputs, and side effects
4. **Handle Cleanup**: Ensure proper resource cleanup
5. **Document Edge Cases**: Clear test descriptions and assertions

### Performance Testing

1. **Set Clear Targets**: Define acceptable performance thresholds
2. **Monitor Resources**: Track memory and CPU usage
3. **Test Concurrency**: Validate concurrent operation handling
4. **Check for Leaks**: Monitor memory growth patterns
5. **Stress Test**: Include edge cases and large files

### Security Testing

1. **Test Input Validation**: All attack vectors and edge cases
2. **Verify Sanitization**: Output content and error messages
3. **Check Permissions**: File and directory access controls
4. **Monitor Exposure**: API keys and sensitive data
5. **Validate Cleanup**: Temporary files and resources

## Troubleshooting

### Common Issues

#### FFmpeg Not Found
```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg

# Verify installation
ffmpeg -version
```

#### Test Data Generation Fails
```bash
# Check FFmpeg availability
python -c "import subprocess; subprocess.run(['ffmpeg', '-version'])"

# Generate with debug output
python tests/e2e/test_data_manager.py --verbose
```

#### Provider Authentication Errors
```bash
# Check API keys
echo $DEEPGRAM_API_KEY
echo $ELEVENLABS_API_KEY

# Test with mocked providers
export TEST_MODE="true"
```

#### Memory Issues During Tests
```bash
# Monitor memory usage
python tests/e2e/run_e2e_tests.py --suite performance --verbose

# Run smaller test suites
python tests/e2e/run_e2e_tests.py --suite unit
```

### Debug Mode

Enable detailed debugging:

```bash
# Maximum verbosity
python tests/e2e/run_e2e_tests.py --verbose --keep-artifacts

# Check logs
tail -f test_results/e2e_test_run.log

# Examine test data
ls -la tests/e2e/test_data/
```

## Production Readiness Criteria

### Acceptance Gates

- ✅ **Functionality**: All core commands work end-to-end
- ✅ **Provider Coverage**: Each transcription provider tested
- ✅ **Error Handling**: Graceful failures with clear messages
- ✅ **Performance**: Meets benchmark targets
- ✅ **Security**: Input validation and output sanitization
- ✅ **Documentation**: Test coverage and usage examples
- ✅ **Monitoring**: Automated test execution and reporting
- ✅ **Regression**: Backward compatibility maintained

### Success Criteria

| Requirement | Target | Measurement |
|-------------|--------|-------------|
| **Test Success Rate** | ≥ 95% | Automated test results |
| **Performance Targets** | Met | Benchmark suite |
| **Security Compliance** | 0 critical issues | Security scan |
| **Code Coverage** | ≥ 90% | Coverage reports |
| **Documentation** | Complete | Manual review |

## Contributing

### Adding New Tests

1. **Choose the Right Suite**: Based on test scope and purpose
2. **Follow Naming Conventions**: Clear, descriptive test names
3. **Use Framework Utilities**: Leverage base classes and mixins
4. **Document Thoroughly**: Clear docstrings and comments
5. **Update Documentation**: Add to this README if needed

### Extending the Framework

1. **Add Base Functionality**: Extend base classes for common patterns
2. **Create Mixins**: Reusable functionality across test classes
3. **Update Test Runner**: Add new suite configurations
4. **Enhance Monitoring**: Add new metrics and alerts
5. **Improve Reporting**: Additional report formats and insights

---

## Support

For issues and questions:
1. Check the [troubleshooting section](#troubleshooting)
2. Review test logs in `test_results/`
3. Run with `--verbose` for detailed output
4. Examine generated test data and reports

The E2E testing framework ensures the `audio-extraction-analysis` tool meets production quality standards through comprehensive validation of all components, integrations, and workflows.