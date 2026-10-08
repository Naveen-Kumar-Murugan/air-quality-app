import 'package:flutter/material.dart';
import '../aqi_colors.dart';

class MapLegend extends StatelessWidget {
  const MapLegend({super.key});

  @override
  Widget build(BuildContext context) {
    return Material(
      elevation: 4,
      borderRadius: BorderRadius.circular(8),
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              'AQI Legend',
              style: TextStyle(
                fontWeight: FontWeight.bold,
                fontSize: 14,
              ),
            ),
            const SizedBox(height: 8),
            ..._buildLegendItems(),
          ],
        ),
      ),
    );
  }

  List<Widget> _buildLegendItems() {
    final categories = [
      ('Good', '0-50'),
      ('Moderate', '51-100'),
      ('USG', '101-150'),
      ('Unhealthy', '151-200'),
      ('Very Unhealthy', '201-300'),
      ('Hazardous', '301+'),
    ];

    return categories.map((item) {
      final category = item.$1;
      final range = item.$2;
      final color = AQICategoryColors.getColor(category);

      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 2),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 20,
              height: 16,
              decoration: BoxDecoration(
                color: color,
                borderRadius: BorderRadius.circular(2),
                border: Border.all(color: Colors.grey.shade400),
              ),
            ),
            const SizedBox(width: 8),
            Text(
              '$category ($range)',
              style: const TextStyle(fontSize: 11),
            ),
          ],
        ),
      );
    }).toList();
  }
}
