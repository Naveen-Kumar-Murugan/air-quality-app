import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:geolocator/geolocator.dart';
import '../../core/api_client.dart';
import '../auth/auth_service.dart';
import 'map_service.dart';
import 'aqi_colors.dart';
import 'widgets/cell_bottom_sheet.dart';
import 'widgets/station_bottom_sheet.dart';

const _darkNavy = Color(0xFF0B1B2B);
const _blue = Color(0xFF2A6FDB);

class MapScreen extends StatefulWidget {
  const MapScreen({super.key});

  @override
  State<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends State<MapScreen> {
  final MapController _mapController = MapController();
  late final MapService _mapService;

  MapDataResponse? _currentData;
  bool _isLoading = false;
  bool _showZoomWarning = false;
  Position? _currentPosition;
  Timer? _fetchTimer;

  String _selectedFilter = 'All Sectors';

  @override
  void initState() {
    super.initState();
    final authService = AuthService();
    final apiClient = ApiClient(authService);
    _mapService = MapService(apiClient);
    mapRefreshNotifier.addListener(_scheduleFetch);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _scheduleFetch();
      _getCurrentLocation();
    });
  }

  @override
  void dispose() {
    mapRefreshNotifier.removeListener(_scheduleFetch);
    _fetchTimer?.cancel();
    super.dispose();
  }

  Future<void> _getCurrentLocation() async {
    try {
      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }
      if (permission == LocationPermission.denied ||
          permission == LocationPermission.deniedForever) {
        return;
      }

      final position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
      );
      if (!mounted) return;

      setState(() {
        _currentPosition = position;
      });

      _mapController.move(
        LatLng(position.latitude, position.longitude),
        15.0,
      );
      _scheduleFetch();
    } catch (_) {
      _scheduleFetch();
    }
  }

  void _onMapEvent(MapEvent event) {
    if (event is MapEventMoveEnd) {
      _scheduleFetch();
    }
  }

  void _scheduleFetch() {
    _fetchTimer?.cancel();
    _fetchTimer = Timer(const Duration(milliseconds: 400), () {
      _fetchMapData();
    });
  }

  Future<void> _fetchMapData() async {
    if (!mounted) return;

    final bounds = _mapController.camera.visibleBounds;
    final zoom = _mapController.camera.zoom.round();

    if (zoom < 11) {
      setState(() {
        _showZoomWarning = true;
        _isLoading = false;
      });
      return;
    }

    setState(() {
      _showZoomWarning = false;
      _isLoading = true;
    });

    try {
      final response = await _mapService.fetchMapData(
        minLon: bounds.west,
        minLat: bounds.south,
        maxLon: bounds.east,
        maxLat: bounds.north,
        zoom: zoom,
      );

      if (!mounted) return;
      setState(() {
        _currentData = response;
        _isLoading = false;
      });
    } on ZoomTooFarOutException {
      if (!mounted) return;
      setState(() {
        _showZoomWarning = true;
        _isLoading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _isLoading = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Could not refresh air quality data.')),
      );
    }
  }

  void _goToMyLocation() {
    if (_currentPosition != null) {
      _mapController.move(
        LatLng(_currentPosition!.latitude, _currentPosition!.longitude),
        15.0,
      );
    } else {
      _getCurrentLocation();
    }
  }

  void _showCellDetails(AirQualityCell cell) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => CellBottomSheet(cell: cell),
    );
  }

  void _showStationDetails(StationMarker station) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => StationBottomSheet(station: station),
    );
  }

  List<Polygon> _buildCellPolygons() {
    if (_currentData == null) return [];

    return _currentData!.cells.map((cell) {
      final color = AQICategoryColors.getColor(cell.category);
      final opacity = (cell.effW / 10).clamp(0.3, 0.9).toDouble();

      return Polygon(
        points: [
          LatLng(cell.south, cell.west),
          LatLng(cell.north, cell.west),
          LatLng(cell.north, cell.east),
          LatLng(cell.south, cell.east),
        ],
        color: color.withValues(alpha: opacity),
        borderColor: color,
        borderStrokeWidth: 1.0,
        isFilled: true,
      );
    }).toList();
  }

  List<Marker> _buildStationMarkers() {
    if (_currentData == null) return [];

    return _currentData!.stations.map((station) {
      final color = AQICategoryColors.getColor(station.category);

      return Marker(
        point: LatLng(station.lat, station.lon),
        width: 44,
        height: 44,
        child: GestureDetector(
          onTap: () => _showStationDetails(station),
          child: Container(
            decoration: BoxDecoration(
              color: Colors.white,
              shape: BoxShape.circle,
              border: Border.all(color: color, width: 3),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.25),
                  blurRadius: 6,
                  offset: const Offset(0, 3),
                ),
              ],
            ),
            child: Center(
              child: Icon(
                Icons.sensors,
                color: color,
                size: 18,
              ),
            ),
          ),
        ),
      );
    }).toList();
  }

  List<Marker> _buildInteractiveAQIMarkers() {
    // Interactive grid-style AQI markers positioned over the map canvas
    // Simulating screen 04 heatmap cell buttons with AQI badges
    final cells = _currentData?.cells ?? [];
    // Show a subset of representative cells as interactive pill markers
    final selected = cells.take(6).toList();
    return selected.asMap().entries.map((entry) {
      final idx = entry.key;
      final cell = entry.value;
      final color = AQICategoryColors.getColor(cell.category);
      final lat = (cell.south + cell.north) / 2;
      final lon = (cell.west + cell.east) / 2;
      // Offset positions to spread across map area for visual variety
      final offsetLat = lat + (idx % 2 == 0 ? 0.001 : -0.001);
      return Marker(
        point: LatLng(offsetLat, lon),
        width: 72,
        height: 56,
        child: GestureDetector(
          onTap: () => _showCellDetails(cell),
          child: Container(
            decoration: BoxDecoration(
              color: Colors.black.withValues(alpha: 0.55),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: color, width: 2),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.35),
                  blurRadius: 8,
                  offset: const Offset(0, 3),
                ),
              ],
            ),
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 8,
                  height: 8,
                  decoration: BoxDecoration(
                    color: color,
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  'AQI ${cell.aqi}',
                  style: TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                    fontSize: 10,
                    letterSpacing: -0.02,
                  ),
                ),
              ],
            ),
          ),
        ),
      );
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _darkNavy,
      body: Stack(
        children: [
          // Hero gradient header
          Positioned(
            top: 0,
            left: 0,
            right: 0,
            child: Container(
              height: 140,
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [_darkNavy, Color(0xFF163a7a)],
                ),
              ),
              padding: const EdgeInsets.fromLTRB(20, 52, 20, 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        width: 40,
                        height: 40,
                        decoration: const BoxDecoration(
                          color: _blue,
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(
                          Icons.camera_alt,
                          color: Colors.white,
                          size: 20,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Skylens',
                            style: TextStyle(
                              fontFamily: 'Space Grotesk',
                              fontSize: 22,
                              fontWeight: FontWeight.bold,
                              color: Colors.white,
                              letterSpacing: -0.03,
                              height: 1.1,
                            ),
                          ),
                          Text(
                            'Air Quality Map',
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w500,
                              color: Colors.white.withValues(alpha: 0.75),
                              letterSpacing: 0.01,
                            ),
                          ),
                        ],
                      ),
                      const Spacer(),
                      // User pill
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(20),
                          border: Border.all(color: Colors.white.withValues(alpha: 0.15)),
                        ),
                        child: Row(
                          children: [
                            const Text(
                              'JD',
                              style: TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.bold,
                                fontSize: 12,
                              ),
                            ),
                            const SizedBox(width: 6),
                            Text(
                              '• 7f3c...5e6f',
                              style: TextStyle(
                                color: Colors.white.withValues(alpha: 0.7),
                                fontSize: 11,
                                fontFamily: 'monospace',
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),

          // Main map
          FlutterMap(
            mapController: _mapController,
            options: MapOptions(
              initialCenter: const LatLng(37.7749, -122.4194),
              initialZoom: 13.0,
              onMapEvent: _onMapEvent,
              onTap: (tapPosition, point) {
                if (_currentData != null) {
                  for (final cell in _currentData!.cells) {
                    if (point.latitude >= cell.south &&
                        point.latitude <= cell.north &&
                        point.longitude >= cell.west &&
                        point.longitude <= cell.east) {
                      _showCellDetails(cell);
                      return;
                    }
                  }
                }
              },
            ),
            children: [
              TileLayer(
                urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                userAgentPackageName: 'com.airquality.app',
              ),
              PolygonLayer(
                polygons: _buildCellPolygons(),
              ),
              MarkerLayer(
                markers: _buildStationMarkers(),
              ),
              // Interactive AQI grid markers (screen 04 style)
              MarkerLayer(
                markers: _buildInteractiveAQIMarkers(),
              ),
              if (_currentPosition != null)
                MarkerLayer(
                  markers: [
                    Marker(
                      point: LatLng(
                        _currentPosition!.latitude,
                        _currentPosition!.longitude,
                      ),
                      width: 24,
                      height: 24,
                      child: Container(
                        decoration: BoxDecoration(
                          color: _blue,
                          shape: BoxShape.circle,
                          border: Border.all(color: Colors.white, width: 2.5),
                          boxShadow: [
                            BoxShadow(
                              color: _blue.withValues(alpha: 0.4),
                              blurRadius: 10,
                              spreadRadius: 2,
                            ),
                          ],
                        ),
                        child: Center(
                          child: Container(
                            width: 8,
                            height: 8,
                            decoration: const BoxDecoration(
                              color: Colors.white,
                              shape: BoxShape.circle,
                            ),
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
            ],
          ),

          // Filter pill tabs (floating over map, screen 04 style)
          Positioned(
            top: 35,
            left: 16,
            right: 16,
            child: Row(
              children: [
                Expanded(
                  child: SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: Row(
                      children: [
                        _buildFilterPill('All Sectors', isActive: _selectedFilter == 'All Sectors'),
                        const SizedBox(width: 8),
                        _buildFilterPill('Cleaner Routes', isActive: _selectedFilter == 'Cleaner Routes'),
                        const SizedBox(width: 8),
                        _buildFilterPill('Sensors', isActive: _selectedFilter == 'Sensors'),
                      ],
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                // Search trigger
              ],
            ),
          ),

          // Legend pill (top-left inside map, screen 04 style)
          Positioned(
            bottom:10,
            left: 16,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.92),
                borderRadius: BorderRadius.circular(24),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.08),
                    blurRadius: 10,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: Row(
                children: [
                  _legendDot(const Color(0xFF00E400), 'Good'),
                  const SizedBox(width: 6),
                  _legendDot(const Color(0xFFFFFF00), 'Mod'),
                  const SizedBox(width: 6),
                  _legendDot(const Color(0xFFFF7E00), 'Sens'),
                  const SizedBox(width: 6),
                  _legendDot(const Color(0xFFFF0000), 'Poor'),
                ],
              ),
            ),
          ),

          // Right floating actions (locate, layer, 3D)
          Positioned(
            bottom: 10,
            right: 16,
            child: Column(
              children: [
                _actionButton(Icons.my_location, onTap: _goToMyLocation),
                const SizedBox(height: 8),
              ],
            ),
          ),

          // Zoom warning
          if (_showZoomWarning)
            Positioned(
              top: 60,
              left: 16,
              right: 16,
              child: Material(
                elevation: 6,
                borderRadius: BorderRadius.circular(16),
                color: Colors.orange.shade700,
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Row(
                    children: [
                      const Icon(Icons.zoom_in, color: Colors.white, size: 22),
                      const SizedBox(width: 10),
                      const Expanded(
                        child: Text(
                          'Zoom in to see air quality data',
                          style: TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.bold,
                            fontSize: 14,
                          ),
                        ),
                      ),
                      IconButton(
                        icon: const Icon(Icons.close, color: Colors.white),
                        onPressed: () => setState(() => _showZoomWarning = false),
                      ),
                    ],
                  ),
                ),
              ),
            ),

          // Loading indicator
          if (_isLoading)
            Positioned(
              top: 200,
              right: 16,
              child: Material(
                elevation: 4,
                borderRadius: BorderRadius.circular(12),
                child: const Padding(
                  padding: EdgeInsets.all(10),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                      SizedBox(width: 8),
                      Text('Loading...'),
                    ],
                  ),
                ),
              ),
            ),


        ],
      ),
    );
  }

  Widget _buildFilterPill(String label, {required bool isActive}) {
    return Material(
      color: isActive
          ? const Color(0xFF0B1B2B)
          : Colors.white.withValues(alpha: 0.92),
      borderRadius: BorderRadius.circular(24),
      elevation: isActive ? 4 : 1,
      shadowColor: Colors.black.withValues(alpha: 0.15),
      child: InkWell(
        onTap: () => setState(() => _selectedFilter = label),
        borderRadius: BorderRadius.circular(24),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (label == 'All Sectors')
                Icon(
                  Icons.layers,
                  size: 16,
                  color: isActive ? Colors.white : _blue,
                ),
              if (label == 'Cleaner Routes')
                Icon(
                  Icons.alt_route,
                  size: 16,
                  color: isActive ? Colors.white : _blue,
                ),
              if (label == 'Sensors')
                Icon(
                  Icons.sensors,
                  size: 16,
                  color: isActive ? Colors.white : Colors.grey.shade600,
                ),
              const SizedBox(width: 6),
              Text(
                label,
                style: TextStyle(
                  fontWeight: FontWeight.w600,
                  fontSize: 13,
                  color: isActive ? Colors.white : const Color(0xFF0B1B2B),
                  letterSpacing: 0.01,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _legendDot(Color color, String text) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(
            color: color,
            shape: BoxShape.circle,
          ),
        ),
        const SizedBox(width: 4),
        Text(
          text,
          style: const TextStyle(
            fontSize: 10,
            fontWeight: FontWeight.w600,
            color: Color(0xFF0B1B2B),
          ),
        ),
      ],
    );
  }

  Widget _actionButton(IconData icon, {required VoidCallback onTap}) {
    return Material(
      color: Colors.white.withValues(alpha: 0.92),
      borderRadius: BorderRadius.circular(50),
      elevation: 2,
      shadowColor: Colors.black.withValues(alpha: 0.08),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(50),
        child: Container(
          width: 44,
          height: 44,
          alignment: Alignment.center,
          child: Icon(icon, color: _darkNavy, size: 20),
        ),
      ),
    );
  }

  Widget _actionButtonText(String text, {required VoidCallback onTap}) {
    return Material(
      color: Colors.white.withValues(alpha: 0.92),
      borderRadius: BorderRadius.circular(50),
      elevation: 2,
      shadowColor: Colors.black.withValues(alpha: 0.08),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(50),
        child: Container(
          width: 44,
          height: 44,
          alignment: Alignment.center,
          child: Text(
            text,
            style: const TextStyle(
              fontWeight: FontWeight.bold,
              fontSize: 12,
              color: _darkNavy,
            ),
          ),
        ),
      ),
    );
  }

  Widget _metaItem({required IconData icon, required String label, required String value}) {
    return Expanded(
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: _blue.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, color: _blue, size: 18),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w600,
                    color: Colors.grey.shade500,
                    letterSpacing: 0.01,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  value,
                  style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    color: Color(0xFF0B1B2B),
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
