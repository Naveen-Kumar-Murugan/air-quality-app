import '../../core/api_client.dart';
import '../routing/route_service.dart';

class CoachService {
  final ApiClient _apiClient;

  CoachService(this._apiClient);

  Future<CoachResponse> sendMessage({
    required String message,
    required double lat,
    required double lon,
    RouteOption? routeResult,
  }) async {
    final Map<String, dynamic> context = {
      'lat': lat,
      'lon': lon,
    };

    if (routeResult != null) {
      context['routeResult'] = {
        'label': routeResult.label,
        'minutes': routeResult.minutes,
        'avgAqi': routeResult.avgAqi,
        'exposure': routeResult.exposure,
        'coverage': routeResult.coverage,
      };
    }

    final payload = {
      'message': message,
      'context': context,
    };

    final data = await _apiClient.post('/coach', payload);
    return CoachResponse.fromJson(data);
  }
}

class CoachResponse {
  final String reply;

  CoachResponse({required this.reply});

  factory CoachResponse.fromJson(Map<String, dynamic> json) {
    return CoachResponse(
      reply: json['reply'] as String? ?? '',
    );
  }
}
