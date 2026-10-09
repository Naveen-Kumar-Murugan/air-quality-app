import 'package:flutter/material.dart';
import 'scan_service.dart';
import '../auth/auth_service.dart';
import '../../core/api_client.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({Key? key}) : super(key: key);

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  late ScanService _scanService;
  List<ScanHistoryItem> _scans = [];
  bool _isLoading = false;
  bool _hasMore = true;
  String? _nextPageToken;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    final authService = AuthService();
    final apiClient = ApiClient(authService);
    _scanService = ScanService(apiClient);
    _loadScans();
  }

  Future<void> _loadScans({bool refresh = false}) async {
    if (_isLoading) return;

    setState(() {
      _isLoading = true;
      _errorMessage = null;
      if (refresh) {
        _scans = [];
        _nextPageToken = null;
        _hasMore = true;
      }
    });

    try {
      final response = await _scanService.getMyScans(
        pageToken: refresh ? null : _nextPageToken,
      );

      setState(() {
        if (refresh) {
          _scans = response.scans;
        } else {
          _scans.addAll(response.scans);
        }
        _nextPageToken = response.nextPageToken;
        _hasMore = response.nextPageToken != null;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _errorMessage = 'Failed to load scans: $e';
        _isLoading = false;
      });
    }
  }

  Future<void> _refresh() async {
    await _loadScans(refresh: true);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF6F9FF),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: _buildBody(),
      ),
    );
  }

  Widget _buildBody() {
    if (_errorMessage != null && _scans.isEmpty) {
      return _buildErrorState();
    }

    if (_scans.isEmpty && _isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_scans.isEmpty) {
      return _buildEmptyState();
    }

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _buildHeader(),
        const SizedBox(height: 24),
        _buildStatsCards(),
        const SizedBox(height: 24),
        _buildSectionHeader(),
        const SizedBox(height: 16),
        ..._scans.map((scan) => _buildScanCard(scan)),
        if (_hasMore && _isLoading)
          const Padding(
            padding: EdgeInsets.all(16.0),
            child: Center(child: CircularProgressIndicator()),
          ),
        const SizedBox(height: 16),
        _buildMeshCalibrationCard(),
      ],
    );
  }

  Widget _buildHeader() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              'Scan History',
              style: TextStyle(
                fontFamily: 'Inter',
                fontSize: 28,
                fontWeight: FontWeight.w700,
                color: const Color(0xFF0D1D2D),
                height: 1.2,
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: const Color(0xFFD8E2FF),
                borderRadius: BorderRadius.circular(20),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.04),
                    blurRadius: 4,
                    offset: const Offset(0, 1),
                  ),
                ],
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    width: 8,
                    height: 8,
                    decoration: BoxDecoration(
                      color: const Color(0xFF0056BB),
                      shape: BoxShape.circle,
                    ),
                  ),
                  const SizedBox(width: 6),
                  Text(
                    '${_scans.length} scans contributed',
                    style: TextStyle(
                      fontFamily: 'Inter',
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: const Color(0xFF004395),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Text(
          'Your local atmospheric contributions',
          style: TextStyle(
            fontFamily: 'Inter',
            fontSize: 14,
            color: const Color(0xFF6B7280),
            height: 1.5,
          ),
        ),
      ],
    );
  }

  Widget _buildStatsCards() {
    final avgAqi = _scans.isEmpty
        ? 0.0
        : _scans.map((s) => s.aqi).reduce((a, b) => a + b) / _scans.length;
    final avgCategory = _getAqiCategory(avgAqi);

    return Row(
      children: [
        Expanded(
          child: Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: const Color(0xFFE3EAF2)),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.04),
                  blurRadius: 4,
                  offset: const Offset(0, 1),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(
                      Icons.eco_outlined,
                      size: 18,
                      color: const Color(0xFF0056BB),
                    ),
                    const SizedBox(width: 6),
                    Text(
                      'Average AQI',
                      style: TextStyle(
                        fontFamily: 'Inter',
                        fontSize: 12,
                        color: const Color(0xFF6B7280),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.baseline,
                  textBaseline: TextBaseline.alphabetic,
                  children: [
                    Text(
                      avgAqi.toStringAsFixed(0),
                      style: TextStyle(
                        fontFamily: 'Space Grotesk',
                        fontSize: 32,
                        fontWeight: FontWeight.w700,
                        color: const Color(0xFF0D1D2D),
                        height: 1.2,
                      ),
                    ),
                    const SizedBox(width: 4),
                    Text(
                      avgCategory,
                      style: TextStyle(
                        fontFamily: 'Inter',
                        fontSize: 12,
                        color: const Color(0xFF6B7280),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  'Across ${_getUniqueZoneCount()} zones',
                  style: TextStyle(
                    fontFamily: 'Inter',
                    fontSize: 13,
                    color: const Color(0xFF00687A),
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: const Color(0xFFE3EAF2)),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.04),
                  blurRadius: 4,
                  offset: const Offset(0, 1),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(
                      Icons.cloud_done_outlined,
                      size: 18,
                      color: const Color(0xFF00687A),
                    ),
                    const SizedBox(width: 6),
                    Text(
                      'Mesh Trust',
                      style: TextStyle(
                        fontFamily: 'Inter',
                        fontSize: 12,
                        color: const Color(0xFF6B7280),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.baseline,
                  textBaseline: TextBaseline.alphabetic,
                  children: [
                    Text(
                      _calculateMeshTrust(),
                      style: TextStyle(
                        fontFamily: 'Space Grotesk',
                        fontSize: 32,
                        fontWeight: FontWeight.w700,
                        color: const Color(0xFF0D1D2D),
                        height: 1.2,
                      ),
                    ),
                    const SizedBox(width: 4),
                    Text(
                      'v2.4',
                      style: TextStyle(
                        fontFamily: 'Inter',
                        fontSize: 12,
                        color: const Color(0xFF6B7280),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  'Sensor aligned',
                  style: TextStyle(
                    fontFamily: 'Inter',
                    fontSize: 13,
                    color: const Color(0xFF0056BB),
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildSectionHeader() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          'Recent Observations',
          style: TextStyle(
            fontFamily: 'Inter',
            fontSize: 16,
            fontWeight: FontWeight.w600,
            color: const Color(0xFF0D1D2D),
          ),
        ),
      ],
    );
  }

  Widget _buildScanCard(ScanHistoryItem scan) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFE3EAF2)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.04),
            blurRadius: 4,
            offset: const Offset(0, 1),
          ),
        ],
      ),
      child: Row(
        children: [
          // Placeholder image - in production this would be the actual scan image
          Container(
            width: 80,
            height: 80,
            decoration: BoxDecoration(
              color: const Color(0xFFE4EFFF),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Stack(
              children: [
                Center(
                  child: Icon(
                    Icons.image_outlined,
                    size: 32,
                    color: const Color(0xFF6B7280),
                  ),
                ),
                Positioned(
                  bottom: 4,
                  right: 4,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
                    decoration: BoxDecoration(
                      color: Colors.black.withOpacity(0.6),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      'HDR',
                      style: TextStyle(
                        fontFamily: 'Inter',
                        fontSize: 10,
                        color: Colors.white,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Expanded(
                      child: Text(
                        _getLocationName(scan.scanId),
                        style: TextStyle(
                          fontFamily: 'Inter',
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                          color: const Color(0xFF0D1D2D),
                        ),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    Icon(
                      Icons.chevron_right,
                      size: 18,
                      color: const Color(0xFF6B7280),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  _formatTimestamp(scan.timestamp),
                  style: TextStyle(
                    fontFamily: 'Inter',
                    fontSize: 13,
                    color: const Color(0xFF6B7280),
                  ),
                ),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    _buildAqiBadge(scan.aqi, scan.category),
                    _buildConfidenceBadge(scan.confidence, scan.source),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAqiBadge(double aqi, String category) {
    final colors = _getAqiBadgeColors(category);
    
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: colors['background'],
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        'AQI ${aqi.toStringAsFixed(0)} • $category',
        style: TextStyle(
          fontFamily: 'Inter',
          fontSize: 12,
          fontWeight: FontWeight.w700,
          color: colors['text'],
        ),
      ),
    );
  }

  Widget _buildConfidenceBadge(double confidence, String source) {
    final isStationBased = source.toLowerCase().contains('station');
    final badgeColor = isStationBased ? const Color(0xFF0056BB) : const Color(0xFF00687A);
    
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: const Color(0xFFEEF4FF),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 6,
            height: 6,
            decoration: BoxDecoration(
              color: badgeColor,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 4),
          Text(
            isStationBased ? 'Estimate • Station Calibrated' : 'Estimate • Model v2.4',
            style: TextStyle(
              fontFamily: 'Inter',
              fontSize: 11,
              color: const Color(0xFF6B7280),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMeshCalibrationCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFFEEF4FF),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFE3EAF2)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.04),
            blurRadius: 4,
            offset: const Offset(0, 1),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  Container(
                    width: 28,
                    height: 28,
                    decoration: BoxDecoration(
                      color: const Color(0xFFD8E2FF),
                      shape: BoxShape.circle,
                    ),
                    child: Icon(
                      Icons.hub_outlined,
                      size: 18,
                      color: const Color(0xFF0056BB),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    'Open Mesh Calibration',
                    style: TextStyle(
                      fontFamily: 'Inter',
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: const Color(0xFF0D1D2D),
                    ),
                  ),
                ],
              ),
              Text(
                'Active',
                style: TextStyle(
                  fontFamily: 'Inter',
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: const Color(0xFF0056BB),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            'Contributing to the open mesh: Every scan anonymously refines microclimate estimates for your neighborhood.',
            style: TextStyle(
              fontFamily: 'Inter',
              fontSize: 14,
              color: const Color(0xFF6B7280),
              height: 1.5,
            ),
          ),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  Container(
                    width: 8,
                    height: 8,
                    decoration: BoxDecoration(
                      color: const Color(0xFF00687A),
                      shape: BoxShape.circle,
                    ),
                  ),
                  const SizedBox(width: 6),
                  Text(
                    'Decentralized verification',
                    style: TextStyle(
                      fontFamily: 'Inter',
                      fontSize: 13,
                      color: const Color(0xFF6B7280),
                    ),
                  ),
                ],
              ),
              Text(
                'Learn more →',
                style: TextStyle(
                  fontFamily: 'Inter',
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: const Color(0xFF0056BB),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        const SizedBox(height: 80),
        Container(
          width: 64,
          height: 64,
          decoration: BoxDecoration(
            color: const Color(0xFFE4EFFF),
            shape: BoxShape.circle,
          ),
          child: Icon(
            Icons.filter_drama_outlined,
            size: 32,
            color: const Color(0xFF0056BB),
          ),
        ),
        const SizedBox(height: 24),
        Text(
          'No Scans Recorded',
          textAlign: TextAlign.center,
          style: TextStyle(
            fontFamily: 'Inter',
            fontSize: 22,
            fontWeight: FontWeight.w600,
            color: const Color(0xFF0D1D2D),
          ),
        ),
        const SizedBox(height: 8),
        Text(
          'The atmosphere is waiting. Capture your first horizon view to benchmark neighborhood particulates.',
          textAlign: TextAlign.center,
          style: TextStyle(
            fontFamily: 'Inter',
            fontSize: 14,
            color: const Color(0xFF6B7280),
            height: 1.5,
          ),
        ),
        const SizedBox(height: 32),
        Center(
          child: ElevatedButton.icon(
            onPressed: () {
              // Navigate to scan screen
            },
            icon: Icon(Icons.photo_camera, size: 18),
            label: Text('Capture Sky Now'),
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF0056BB),
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(24),
              ),
              elevation: 2,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildErrorState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.error_outline,
              size: 64,
              color: const Color(0xFFBA1A1A),
            ),
            const SizedBox(height: 16),
            Text(
              _errorMessage!,
              textAlign: TextAlign.center,
              style: TextStyle(
                fontFamily: 'Inter',
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: const Color(0xFF0D1D2D),
              ),
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: () => _loadScans(refresh: true),
              icon: Icon(Icons.refresh),
              label: Text('Retry'),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF0056BB),
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(24),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Map<String, Color> _getAqiBadgeColors(String category) {
    switch (category.toLowerCase()) {
      case 'good':
        return {
          'background': const Color(0xFFADECFF),
          'text': const Color(0xFF005F70),
        };
      case 'moderate':
        return {
          'background': const Color(0xFFADECFF),
          'text': const Color(0xFF001F26),
        };
      case 'unhealthy for sensitive groups':
      case 'unhealthy sg':
        return {
          'background': const Color(0xFFFFDBC9),
          'text': const Color(0xFF321200),
        };
      case 'unhealthy':
        return {
          'background': const Color(0xFFBA1A1A),
          'text': Colors.white,
        };
      case 'very unhealthy':
        return {
          'background': const Color(0xFF8F3F97),
          'text': Colors.white,
        };
      case 'hazardous':
        return {
          'background': const Color(0xFF7E0023),
          'text': Colors.white,
        };
      default:
        return {
          'background': const Color(0xFFE3EAF2),
          'text': const Color(0xFF0D1D2D),
        };
    }
  }

  String _getAqiCategory(double aqi) {
    if (aqi <= 50) return 'Good';
    if (aqi <= 100) return 'Mod';
    if (aqi <= 150) return 'USG';
    if (aqi <= 200) return 'Unh';
    if (aqi <= 300) return 'V.Unh';
    return 'Haz';
  }

  String _calculateMeshTrust() {
    if (_scans.isEmpty) return '0%';
    final avgConfidence = _scans.map((s) => s.confidence).reduce((a, b) => a + b) / _scans.length;
    return '${(avgConfidence * 100).toStringAsFixed(0)}%';
  }

  int _getUniqueZoneCount() {
    // Simplified - in production would track actual unique locations
    return (_scans.length / 1.5).ceil().clamp(1, _scans.length);
  }

  String _getLocationName(String scanId) {
    // Placeholder - in production this would come from reverse geocoding
    final locations = [
      'Cubbon Park West Gate',
      'Indiranagar 100ft Road',
      'Whitefield Main Road',
      'Silk Board Junction',
      'MG Road',
      'Koramangala 5th Block',
    ];
    return locations[scanId.hashCode % locations.length];
  }

  String _formatTimestamp(DateTime timestamp) {
    final now = DateTime.now();
    final difference = now.difference(timestamp);
    
    if (difference.inDays == 0) {
      final hour = timestamp.hour;
      final minute = timestamp.minute.toString().padLeft(2, '0');
      final period = hour >= 12 ? 'PM' : 'AM';
      final displayHour = hour > 12 ? hour - 12 : (hour == 0 ? 12 : hour);
      return 'Today, $displayHour:$minute $period';
    } else if (difference.inDays == 1) {
      final hour = timestamp.hour;
      final minute = timestamp.minute.toString().padLeft(2, '0');
      final period = hour >= 12 ? 'PM' : 'AM';
      final displayHour = hour > 12 ? hour - 12 : (hour == 0 ? 12 : hour);
      return 'Yesterday, $displayHour:$minute $period';
    } else {
      final months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
      final hour = timestamp.hour;
      final minute = timestamp.minute.toString().padLeft(2, '0');
      final period = hour >= 12 ? 'PM' : 'AM';
      final displayHour = hour > 12 ? hour - 12 : (hour == 0 ? 12 : hour);
      return '${months[timestamp.month - 1]} ${timestamp.day}, $displayHour:$minute $period';
    }
  }
}
