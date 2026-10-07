import 'package:flutter/material.dart';

class AqiChip extends StatelessWidget {
  final String category;
  final bool large;

  const AqiChip({
    Key? key,
    required this.category,
    this.large = false,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final colors = _getCategoryColors(category);
    final fontSize = large ? 24.0 : 14.0;
    final padding = large
        ? const EdgeInsets.symmetric(horizontal: 24, vertical: 12)
        : const EdgeInsets.symmetric(horizontal: 12, vertical: 6);

    return Container(
      padding: padding,
      decoration: BoxDecoration(
        color: colors['background'],
        borderRadius: BorderRadius.circular(large ? 16 : 12),
        border: Border.all(
          color: colors['border']!,
          width: 2,
        ),
      ),
      child: Text(
        category,
        style: TextStyle(
          color: colors['text'],
          fontSize: fontSize,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }

  Map<String, Color> _getCategoryColors(String category) {
    switch (category.toLowerCase()) {
      case 'good':
        return {
          'background': const Color(0xFF00E400),
          'border': const Color(0xFF00B300),
          'text': Colors.white,
        };
      case 'moderate':
        return {
          'background': const Color(0xFFFFFF00),
          'border': const Color(0xFFCCCC00),
          'text': Colors.black,
        };
      case 'unhealthy for sensitive groups':
      case 'unhealthy sg':
        return {
          'background': const Color(0xFFFF7E00),
          'border': const Color(0xFFCC6500),
          'text': Colors.white,
        };
      case 'unhealthy':
        return {
          'background': const Color(0xFFFF0000),
          'border': const Color(0xFFCC0000),
          'text': Colors.white,
        };
      case 'very unhealthy':
        return {
          'background': const Color(0xFF8F3F97),
          'border': const Color(0xFF6F2F77),
          'text': Colors.white,
        };
      case 'hazardous':
        return {
          'background': const Color(0xFF7E0023),
          'border': const Color(0xFF5E0013),
          'text': Colors.white,
        };
      default:
        return {
          'background': Colors.grey,
          'border': Colors.grey.shade700,
          'text': Colors.white,
        };
    }
  }
}
