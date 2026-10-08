import 'package:flutter_test/flutter_test.dart';
import 'package:air_quality_app/features/map/aqi_colors.dart';

void main() {
  group('AQICategoryColors', () {
    test('getColor returns correct colors for categories', () {
      expect(AQICategoryColors.getColor('Good'), isNotNull);
      expect(AQICategoryColors.getColor('Moderate'), isNotNull);
      expect(AQICategoryColors.getColor('USG'), isNotNull);
      expect(AQICategoryColors.getColor('Unsafe'),
          AQICategoryColors.getColor('Good'));
    });

    test('getCategory classifies AQI correctly', () {
      expect(AQICategoryColors.getCategory(25), equals('Good'));
      expect(AQICategoryColors.getCategory(75), equals('Moderate'));
      expect(AQICategoryColors.getCategory(125), equals('USG'));
      expect(AQICategoryColors.getCategory(175), equals('Unhealthy'));
      expect(AQICategoryColors.getCategory(250), equals('Very Unhealthy'));
      expect(AQICategoryColors.getCategory(350), equals('Hazardous'));
    });
  });
}
