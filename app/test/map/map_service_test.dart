import 'package:flutter_test/flutter_test.dart';
import 'package:air_quality_app/features/map/map_service.dart';

void main() {
  group('MapDataResponse', () {
    test('parses the GET /map response contract', () {
      final response = MapDataResponse.fromJson({
        'res': 7,
        'cells': [
          {
            'id': 'tdr1wxy',
            'centre': [37.7749, -122.4194],
            'bounds': [37.77, -122.42, 37.78, -122.41],
            'aqi': 85,
            'category': 'Moderate',
            'n': 6,
            'effW': 2.3,
            'updatedAt': '2026-01-01T12:00:00Z',
          },
        ],
        'stations': [
          {
            'id': 'st1',
            'name': 'Test Station',
            'lat': 37.7749,
            'lon': -122.4194,
            'aqi': 120,
            'measuredAt': '2026-01-01T12:00:00Z',
          },
        ],
      });

      expect(response.resolution, 7);
      expect(response.cells.single.latitude, 37.7749);
      expect(response.cells.single.longitude, -122.4194);
      expect(response.cells.single.south, 37.77);
      expect(response.cells.single.effW, 2.3);
      expect(response.stations.single.category, 'USG');
    });
  });
}
