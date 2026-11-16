# LaCrosse / HyperOS R6

R6 fixes two objective sender-FPS telemetry false positives: duplicate CarLife timestamps are valid, and slow-frame thresholds scale to the negotiated target (30 fps 50ms, 60 fps 25ms). The existing Apple-inspired UI is retained; settings contrast, 48dp segmented touch targets, 48dp settings back button, and header legibility are improved.

R6 remains experimental. It does not promise actual 60Hz display, nor merge every earlier R3 patch. Cloud build runs tests, lint and APK compilation; hardware validation is still required. See `.github/workflows/build-lacrosse-r6-apk.yml`.
