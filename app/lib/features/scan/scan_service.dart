import 'dart:typed_data';
import 'package:dio/dio.dart';
import '../../core/api_client.dart';

class ScanService {
  final ApiClient _apiClient;
  late final Dio _dio;

  ScanService(this._apiClient) {
    _dio = Dio();
  }

  Future<UploadUrlResponse> getUploadUrl() async {
    try {
      final response = await _apiClient.post('/scans/upload-url', {});
      return UploadUrlResponse.fromJson(response);
    } on DioException catch (e) {
      if (e.response?.statusCode == 429) {
        throw RateLimitException(
            'You have reached the scan limit. Please try again later.');
      }
      rethrow;
    }
  }

  Future<void> uploadImage(String uploadUrl, Uint8List imageBytes) async {
    await _dio.put(
      uploadUrl,
      data: imageBytes,
      options: Options(
        headers: {
          'Content-Type': 'image/jpeg',
        },
        contentType: 'image/jpeg',
      ),
    );
  }

  Future<ScanResult> submitScan(ScanSubmission submission) async {
    int retries = 0;
    const maxRetries = 3;

    while (retries < maxRetries) {
      try {
        final response = await _apiClient.post('/scans', submission.toJson());
        return ScanResult.fromJson(response);
      } on DioException catch (e) {
        if (e.response?.statusCode == 429) {
          throw RateLimitException(
              'Rate limit exceeded. Please try again later.');
        }
        
        retries++;
        if (retries >= maxRetries) {
          rethrow;
        }
        await Future.delayed(Duration(seconds: retries));
      }
    }
    
    throw Exception('Failed to submit scan after $maxRetries retries');
  }

  Future<ScanHistoryResponse> getMyScans({String? pageToken}) async {
    final queryParams = pageToken != null ? {'pageToken': pageToken} : null;
    final response = await _apiClient.get('/scans/mine', queryParams: queryParams);
    return ScanHistoryResponse.fromJson(response);
  }
}

class UploadUrlResponse {
  final String scanId;
  final String uploadUrl;
  final String s3Key;

  UploadUrlResponse({
    required this.scanId,
    required this.uploadUrl,
    required this.s3Key,
  });

  factory UploadUrlResponse.fromJson(Map<String, dynamic> json) {
    return UploadUrlResponse(
      scanId: json['scanId'] as String,
      uploadUrl: json['uploadUrl'] as String,
      s3Key: json['s3Key'] as String,
    );
  }
}

class ScanSubmission {
  final String scanId;
  final String s3Key;
  final double lat;
  final double lon;
  final double accuracy;
  final double? pressure;
  final String? tag;
  final DateTime timestamp;

  ScanSubmission({
    required this.scanId,
    required this.s3Key,
    required this.lat,
    required this.lon,
    required this.accuracy,
    this.pressure,
    this.tag,
    required this.timestamp,
  });

  Map<String, dynamic> toJson() {
    return {
      'scanId': scanId,
      's3Key': s3Key,
      'lat': lat,
      'lon': lon,
      'accuracy': accuracy,
      if (pressure != null) 'pressure': pressure,
      if (tag != null) 'tag': tag,
      'timestamp': _toIstIso(timestamp),
    };
  }

  String _toIstIso(DateTime time) {
    final ist = time.toUtc().add(const Duration(hours: 5, minutes: 30));
    return '${ist.toIso8601String().replaceFirst('Z', '')}+05:30';
  }
}

class ScanResult {
  final String scanId;
  final double aqi;
  final String category;
  final double confidence;
  final String source;
  final StationInfo? station;

  ScanResult({
    required this.scanId,
    required this.aqi,
    required this.category,
    required this.confidence,
    required this.source,
    this.station,
  });

  factory ScanResult.fromJson(Map<String, dynamic> json) {
    return ScanResult(
      scanId: json['scanId'] as String,
      aqi: (json['aqi'] as num).toDouble(),
      category: json['category'] as String,
      confidence: (json['confidence'] as num).toDouble(),
      source: json['source'] as String,
      station: json['station'] != null
          ? StationInfo.fromJson(json['station'] as Map<String, dynamic>)
          : null,
    );
  }
}

class StationInfo {
  final String name;
  final double distance;
  final double aqi;

  StationInfo({
    required this.name,
    required this.distance,
    required this.aqi,
  });

  factory StationInfo.fromJson(Map<String, dynamic> json) {
    return StationInfo(
      name: json['name'] as String,
      distance: (json['distance'] as num).toDouble(),
      aqi: (json['aqi'] as num).toDouble(),
    );
  }
}

class ScanHistoryResponse {
  final List<ScanHistoryItem> scans;
  final String? nextPageToken;

  ScanHistoryResponse({
    required this.scans,
    this.nextPageToken,
  });

  factory ScanHistoryResponse.fromJson(Map<String, dynamic> json) {
    return ScanHistoryResponse(
      scans: (json['scans'] as List)
          .map((item) => ScanHistoryItem.fromJson(item as Map<String, dynamic>))
          .toList(),
      nextPageToken: json['nextPageToken'] as String?,
    );
  }
}

class ScanHistoryItem {
  final String scanId;
  final double aqi;
  final String category;
  final double confidence;
  final String source;
  final DateTime timestamp;

  ScanHistoryItem({
    required this.scanId,
    required this.aqi,
    required this.category,
    required this.confidence,
    required this.source,
    required this.timestamp,
  });

  factory ScanHistoryItem.fromJson(Map<String, dynamic> json) {
    return ScanHistoryItem(
      scanId: json['scanId'] as String,
      aqi: (json['aqi'] as num).toDouble(),
      category: json['category'] as String,
      confidence: (json['confidence'] as num).toDouble(),
      source: json['source'] as String,
      timestamp: DateTime.parse(json['timestamp'] as String),
    );
  }
}

class RateLimitException implements Exception {
  final String message;
  RateLimitException(this.message);

  @override
  String toString() => message;
}
