import 'package:flutter/material.dart';
import '../scan_service.dart';
import '../../auth/auth_service.dart';
import '../../core/api_client.dart';
import 'widgets/aqi_chip.dart';
import 'widgets/confidence_indicator.dart';

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
    return RefreshIndicator(
      onRefresh: _refresh,
      child: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_errorMessage != null && _scans.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.error_outline, size: 64, color: Colors.red),
              const SizedBox(height: 16),
              Text(
                _errorMessage!,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 24),
              ElevatedButton.icon(
                onPressed: () => _loadScans(refresh: true),
                icon: const Icon(Icons.refresh),
                label: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    if (_scans.isEmpty && _isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_scans.isEmpty) {
      return ListView(
        children: [
          Padding(
            padding: const EdgeInsets.all(24.0),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const SizedBox(height: 80),
                Icon(
                  Icons.camera_alt_outlined,
                  size: 120,
                  color: Colors.grey.shade400,
                ),
                const SizedBox(height: 24),
                Text(
                  'No scans yet',
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        color: Colors.grey.shade600,
                      ),
                ),
                const SizedBox(height: 8),
                Text(
                  'Take your first air quality scan',
                  style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                        color: Colors.grey.shade500,
                      ),
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),
        ],
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _scans.length + (_hasMore ? 1 : 0),
      itemBuilder: (context, index) {
        if (index == _scans.length) {
          if (!_isLoading) {
            _loadScans();
          }
          return const Padding(
            padding: EdgeInsets.all(16.0),
            child: Center(child: CircularProgressIndicator()),
          );
        }

        final scan = _scans[index];
        return _buildScanCard(scan);
      },
    );
  }

  Widget _buildScanCard(ScanHistoryItem scan) {
    final sourceBadge = _getSourceBadge(scan.source);
    final timeAgo = _formatTimeAgo(scan.timestamp);

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                AqiChip(category: scan.category),
                Text(
                  timeAgo,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Colors.grey.shade600,
                      ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'AQI',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              color: Colors.grey.shade600,
                            ),
                      ),
                      Text(
                        scan.aqi.toStringAsFixed(0),
                        style: Theme.of(context).textTheme.titleLarge?.copyWith(
                              fontWeight: FontWeight.bold,
                            ),
                      ),
                    ],
                  ),
                ),
                Expanded(
                  flex: 2,
                  child: ConfidenceIndicator(
                    confidence: scan.confidence,
                    showLabel: false,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: Colors.blue.shade50,
                borderRadius: BorderRadius.circular(4),
                border: Border.all(color: Colors.blue.shade200),
              ),
              child: Text(
                sourceBadge,
                style: TextStyle(
                  color: Colors.blue.shade900,
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ),
      ),
    );
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

  String _formatTimeAgo(DateTime timestamp) {
    final now = DateTime.now();
    final difference = now.difference(timestamp);

    if (difference.inDays > 0) {
      return '${difference.inDays}d ago';
    } else if (difference.inHours > 0) {
      return '${difference.inHours}h ago';
    } else if (difference.inMinutes > 0) {
      return '${difference.inMinutes}m ago';
    } else {
      return 'Just now';
    }
  }
}
