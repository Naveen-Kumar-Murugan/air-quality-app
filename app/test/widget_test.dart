import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:air_quality_app/features/map/widgets/map_legend.dart';

void main() {
  testWidgets('Map legend shows all six AQI categories', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: Scaffold(body: MapLegend())));

    expect(find.text('AQI Legend'), findsOneWidget);
    expect(find.text('Good (0-50)'), findsOneWidget);
    expect(find.text('Moderate (51-100)'), findsOneWidget);
    expect(find.text('USG (101-150)'), findsOneWidget);
    expect(find.text('Unhealthy (151-200)'), findsOneWidget);
    expect(find.text('Very Unhealthy (201-300)'), findsOneWidget);
    expect(find.text('Hazardous (301+)'), findsOneWidget);
  });
}
