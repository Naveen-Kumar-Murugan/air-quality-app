import '../../core/api_client.dart';

class RouteService {
  final ApiClient _apiClient;

  RouteService(this._apiClient);

  Future<RouteResponse> fetchRoute({
    required double originLat,
    required double originLon,
    required double destLat,
    required double destLon,
    required String mode,
  }) async {
    final payload = {
      'origin': {'lat': originLat, 'lon': originLon},
      'destination': {'lat': destLat, 'lon': destLon},
      'mode': mode,
    };
    final data = await _apiClient.post('/route', payload);
    return RouteResponse.fromJson(data);
  }
}

class RouteResponse {
  final List<RouteOption> routes;

  RouteResponse({required this.routes});

  factory RouteResponse.fromJson(Map<String, dynamic> json) {
    final routesJson = json['routes'] as List<dynamic>? ?? [];
    return RouteResponse(
      routes: routesJson.map((r) => RouteOption.fromJson(r as Map<String, dynamic>)).toList(),
    );
  }
}

class RouteOption {
  final String label;
  final List<List<double>> polyline;
  final int minutes;
  final double avgAqi;
  final double exposure;
  final double coverage;
  final List<RouteSegment> segments;

  RouteOption({
    required this.label,
    required this.polyline,
    required this.minutes,
    required this.avgAqi,
    required this.exposure,
    required this.coverage,
    required this.segments,
  });

  factory RouteOption.fromJson(Map<String, dynamic> json) {
    final segmentsJson = json['segments'] as List<dynamic>? ?? [];
    return RouteOption(
      label: json['label'] as String? ?? '',
      polyline: (json['polyline'] as List<dynamic>? ?? [])
          .map((pt) => (pt as List<dynamic>).map((v) => (v as num).toDouble()).toList())
          .toList(),
      minutes: json['minutes'] as int? ?? 0,
      avgAqi: (json['avgAqi'] as num?)?.toDouble() ?? 0.0,
      exposure: (json['exposure'] as num?)?.toDouble() ?? 0.0,
      coverage: (json['coverage'] as num?)?.toDouble() ?? 0.0,
      segments: segmentsJson.map((s) => RouteSegment.fromJson(s as Map<String, dynamic>)).toList(),
    );
  }
}

class RouteSegment {
  final List<List<double>> points;
  final double aqi;

  RouteSegment({required this.points, required this.aqi});

  factory RouteSegment.fromJson(Map<String, dynamic> json) {
    return RouteSegment(
      points: (json['points'] as List<dynamic>? ?? [])
          .map((pt) => (pt as List<dynamic>).map((v) => (v as num).toDouble()).toList())
          .toList(),
      aqi: (json['aqi'] as num?)?.toDouble() ?? 0.0,
    );
  }
}
