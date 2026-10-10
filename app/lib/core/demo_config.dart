import 'package:flutter/material.dart';

import 'config.dart';

/// Bundled sample sky photos and the fixed location used when the app is
/// built with `--dart-define=DEMO=true`. Demo mode replaces the camera with a
/// picker of these images and skips live GPS, so the web demo runs without any
/// browser permission prompts while still exercising the real upload -> scan ->
/// map pipeline.
class DemoConfig {
  /// Fixed demo location: central Bengaluru (near the seeded Cubbon Park cell).
  static const double latitude = 12.9763;
  static const double longitude = 77.5929;
  static const double accuracyMeters = 12.0;

  /// Whether the app is running in demo mode.
  static bool get enabled => Config.isDemo;

  /// Sample photos shown in the demo picker, in order.
  static const List<DemoSample> samples = [
    DemoSample('assets/demo/clear.jpg', 'Clear sky', 'Good', Icons.wb_sunny),
    DemoSample('assets/demo/hazy.jpg', 'Hazy urban', 'Moderate', Icons.cloud),
    DemoSample('assets/demo/smoky.jpg', 'Smog plume', 'Unhealthy', Icons.fireplace),
    DemoSample('assets/demo/overcast.jpg', 'Overcast', 'Moderate', Icons.cloud_queue),
    DemoSample('assets/demo/sunset.jpg', 'Sunset horizon', 'Sensitive', Icons.wb_twilight),
    DemoSample('assets/demo/window.jpg', 'Indoors (window)', 'Good', Icons.window),
  ];
}

class DemoSample {
  final String asset;
  final String label;
  final String aqiHint;
  final IconData icon;

  const DemoSample(this.asset, this.label, this.aqiHint, this.icon);
}

