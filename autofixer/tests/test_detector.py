from autofixer.detector import AnomalyDetector


def test_detector_requires_minimum_samples():
    detector = AnomalyDetector(std_dev_multiplier=2.0, min_samples=5)
    anomaly = detector.detect(
        kind="transition",
        metric_key="transition:Proc:act",
        observed=100.0,
        samples=[1.0, 1.1, 0.9, 1.0],
        fingerprint="x",
        details={},
    )
    assert anomaly is None


def test_detector_detects_outlier():
    detector = AnomalyDetector(std_dev_multiplier=2.0, min_samples=5)
    anomaly = detector.detect(
        kind="transition",
        metric_key="transition:Proc:act",
        observed=10.0,
        samples=[1.0, 1.2, 1.1, 0.9, 1.0, 1.05],
        fingerprint="x",
        details={},
    )
    assert anomaly is not None
    assert anomaly.threshold < anomaly.observed

