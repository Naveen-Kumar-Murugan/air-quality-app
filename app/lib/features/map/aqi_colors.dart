import 'package:flutter/material.dart';

class AQICategoryColors {
  static const Map<String, Color> colors = {
    'Good': Color(0xFF00E400),
    'Moderate': Color(0xFFFFFF00),
    'USG': Color(0xFFFF7E00),
    'Unhealthy': Color(0xFFFF0000),
    'Very Unhealthy': Color(0xFF8F3F97),
    'Hazardous': Color(0xFF7E0023),
  };

  static Color getColor(String category) {
    return colors[category] ?? colors['Good']!;
  }

  static String getCategory(int aqi) {
    if (aqi <= 50) return 'Good';
    if (aqi <= 100) return 'Moderate';
    if (aqi <= 150) return 'USG';
    if (aqi <= 200) return 'Unhealthy';
    if (aqi <= 300) return 'Very Unhealthy';
    return 'Hazardous';
  }

  static String getCategoryDescription(String category) {
    switch (category) {
      case 'Good':
        return 'Air quality is satisfactory';
      case 'Moderate':
        return 'Acceptable air quality';
      case 'USG':
        return 'Members of sensitive groups may experience health effects';
      case 'Unhealthy':
        return 'Some members of the general public may begin to experience health effects';
      case 'Very Unhealthy':
        return 'Members of the general public may begin to experience serious health effects';
      case 'Hazardous':
        return 'Health alert: entire population is more likely to be affected';
      default:
        return '';
    }
  }
}
