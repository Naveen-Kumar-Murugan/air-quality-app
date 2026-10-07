import 'package:flutter/material.dart';
import 'scan_service.dart';
import 'widgets/aqi_chip.dart';
import 'widgets/confidence_indicator.dart';

class ResultScreen extends StatelessWidget {
  final ScanResult result;

  const ResultScreen({
    Key? key,
    required this.result,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final aqiRange = _getAqiRange(result.aqi, result.category);
    final sourceBadge = _getSourceBadge(result.source);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Scan Result'),
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const SizedBox(height: 24),
            Center(
              child: AqiChip(
                category: result.category,
                large: true,
              ),
            ),
            const SizedBox(height: 32),
            Card(
              elevation: 2,
              child: Padding(
                padding: const EdgeInsets.all(20.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.thermostat, size: 32, color: Colors.blue),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'AQI Estimate',
                                style: Theme.of(context).textTheme.titleSmall?.copyWith(
                                      color: Colors.grey.shade600,
                                    ),
                              ),
                              Text(
                                aqiRange,
                                style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                                      fontWeight: FontWeight.bold,
                                    ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 24),
                    ConfidenceIndicator(confidence: result.confidence),
                    const SizedBox(height: 24),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                      decoration: BoxDecoration(
                        color: Colors.blue.shade50,
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: Colors.blue.shade200),
                      ),
                      child: Row(
                        children: [
                          Icon(Icons.info_outline, size: 20, color: Colors.blue.shade700),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              sourceBadge,
                              style: TextStyle(
                                color: Colors.blue.shade900,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
            if (result.station != null) ...[
              const SizedBox(height: 24),
              Card(
                elevation: 2,
                child: Padding(
                  padding: const EdgeInsets.all(20.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Icon(Icons.location_on, size: 28, color: Colors.green.shade700),
                          const SizedBox(width: 12),
                          Text(
                            'Nearest Station',
                            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                                  fontWeight: FontWeight.bold,
                                ),
                          ),
                        ],
                      ),
                      const Divider(height: 24),
                      _buildStationRow(
                        context,
                        'Name',
                        result.station!.name,
                        Icons.sensors,
                      ),
                      const SizedBox(height: 12),
                      _buildStationRow(
                        context,
                        'Distance',
                        '${result.station!.distance.toStringAsFixed(1)} km',
                        Icons.straighten,
                      ),
                      const SizedBox(height: 12),
                      _buildStationRow(
                        context,
                        'Station AQI',
                        result.station!.aqi.toStringAsFixed(0),
                        Icons.air,
                      ),
                    ],
                  ),
                ),
              ),
            ],
            const SizedBox(height: 32),
            SizedBox(
              width: double.infinity,
              height: 48,
              child: ElevatedButton.icon(
                onPressed: () {
                  Navigator.of(context).popUntil((route) => route.isFirst);
                },
                icon: const Icon(Icons.home),
                label: const Text(
                  'Back to Home',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                ),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.blue,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(24),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStationRow(BuildContext context, String label, String value, IconData icon) {
    return Row(
      children: [
        Icon(icon, size: 20, color: Colors.grey.shade600),
        const SizedBox(width: 8),
        Text(
          '$label: ',
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Colors.grey.shade600,
              ),
        ),
        Expanded(
          child: Text(
            value,
            style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
          ),
        ),
      ],
    );
  }

  String _getAqiRange(double aqi, String category) {
    final ranges = {
      'Good': '0-50',
      'Moderate': '51-100',
      'Unhealthy for Sensitive Groups': '101-150',
      'Unhealthy SG': '101-150',
      'Unhealthy': '151-200',
      'Very Unhealthy': '201-300',
      'Hazardous': '301+',
    };

    final categoryRange = ranges[category] ?? ranges['Moderate']!;
    final midpoint = aqi.round();
    
    return '$categoryRange (≈$midpoint)';
  }

  String _getSourceBadge(String source) {
    if (source.contains('station')) {
      return 'Station-based estimate';
    } else if (source.contains('model')) {
      return 'Model estimate';
    } else {
      return 'Estimated';
    }
  }
}
