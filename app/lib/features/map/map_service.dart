import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import '../../core/api_client.dart';

final ValueNotifier<int> mapRefreshNotifier = ValueNotifier<int>(0);

void notifyMapRefresh() {
  mapRefreshNotifier.value++;
}

class MapService {
  final ApiClient _apiClient;

  MapService(this._apiClient);

  Future<MapDataResponse> fetchMapData({
    required double minLon,
    required double minLat,
    required double maxLon,
    required double maxLat,
    required int zoom,
  }) async {
    final queryParams = {
      'bbox': '$minLon,$minLat,$maxLon,$maxLat',
      'zoom': zoom.toString(),
    };

    try {
      final response = await _apiClient.get('/map', queryParams: queryParams);
      return MapDataResponse.fromJson(response);
    } on DioException catch (error) {
      if (error.response?.statusCode == 400) {
        throw ZoomTooFarOutException();
      }
      rethrow;
    }
  }
}

class MapDataResponse {
  final int resolution;
  final List<AirQualityCell> cells;
  final List<StationMarker> stations;

  MapDataResponse({
    required this.resolution,
    required this.cells,
    required this.stations,
  });

  factory MapDataResponse.fromJson(Map<String, dynamic> json) {
    return MapDataResponse(
      resolution: json['res'] as int,
      cells: (json['cells'] as List<dynamic>)
          .map((cell) => AirQualityCell.fromJson(cell as Map<String, dynamic>))
          .toList(),
      stations: (json['stations'] as List<dynamic>)
          .map((station) =>
              StationMarker.fromJson(station as Map<String, dynamic>))
          .toList(),
    );
  }
}

class AirQualityCell {
  final String id;
  final List<double> centre;
  final List<double> bounds;
  final int aqi;
  final String category;
  final int n;
  final double effW;
  final String updatedAt;

  AirQualityCell({
    required this.id,
    required this.centre,
    required this.bounds,
    required this.aqi,
    required this.category,
    required this.n,
    required this.effW,
    required this.updatedAt,
  });

  factory AirQualityCell.fromJson(Map<String, dynamic> json) {
    return AirQualityCell(
      id: json['id'] as String,
      centre:
          (json['centre'] as List).map((e) => (e as num).toDouble()).toList(),
      bounds:
          (json['bounds'] as List).map((e) => (e as num).toDouble()).toList(),
      aqi: json['aqi'] as int,
      category: json['category'] as String,
      n: json['n'] as int,
      effW: (json['effW'] as num).toDouble(),
      updatedAt: json['updatedAt'] as String,
    );
  }

  double get latitude => centre[0];
  double get longitude => centre[1];
  double get south => bounds[0];
  double get west => bounds[1];
  double get north => bounds[2];
  double get east => bounds[3];
}

class StationMarker {
  final String id;
  final String name;
  final double lat;
  final double lon;
  final int aqi;
  final String measuredAt;

  StationMarker({
    required this.id,
    required this.name,
    required this.lat,
    required this.lon,
    required this.aqi,
    required this.measuredAt,
  });

  factory StationMarker.fromJson(Map<String, dynamic> json) {
    return StationMarker(
      id: json['id'] as String,
      name: json['name'] as String,
      lat: (json['lat'] as num).toDouble(),
      lon: (json['lon'] as num).toDouble(),
      aqi: json['aqi'] as int,
      measuredAt: json['measuredAt'] as String,
    );
  }

  String get category {
    if (aqi <= 50) return 'Good';
    if (aqi <= 100) return 'Moderate';
    if (aqi <= 150) return 'USG';
    if (aqi <= 200) return 'Unhealthy';
    if (aqi <= 300) return 'Very Unhealthy';
    return 'Hazardous';
  }
}

class ZoomTooFarOutException implements Exception {
  @override
  String toString() => 'Zoom level too far out';
}
