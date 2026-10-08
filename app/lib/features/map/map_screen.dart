import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:geolocator/geolocator.dart';
import '../../core/api_client.dart';
import '../auth/auth_service.dart';
import 'map_service.dart';
import 'aqi_colors.dart';
import 'widgets/map_legend.dart';
import 'widgets/cell_bottom_sheet.dart';
import 'widgets/station_bottom_sheet.dart';

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
      builder: (context) => CellBottomSheet(cell: cell),
    );
  }

  void _showStationDetails(StationMarker station) {
    showModalBottomSheet(
      context: context,
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
        width: 40,
        height: 40,
        child: GestureDetector(
          onTap: () => _showStationDetails(station),
          child: Container(
            decoration: BoxDecoration(
              color: Colors.white,
              shape: BoxShape.circle,
              border: Border.all(color: color, width: 3),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.3),
                  blurRadius: 4,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: Center(
              child: Icon(
                Icons.sensors,
                color: color,
                size: 20,
              ),
            ),
          ),
        ),
      );
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        children: [
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
              if (_currentPosition != null)
                MarkerLayer(
                  markers: [
                    Marker(
                      point: LatLng(
                        _currentPosition!.latitude,
                        _currentPosition!.longitude,
                      ),
                      width: 20,
                      height: 20,
                      child: Container(
                        decoration: BoxDecoration(
                          color: Colors.blue,
                          shape: BoxShape.circle,
                          border: Border.all(color: Colors.white, width: 2),
                          boxShadow: [
                            BoxShadow(
                              color: Colors.black.withValues(alpha: 0.3),
                              blurRadius: 4,
                              offset: const Offset(0, 2),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
            ],
          ),
          if (_showZoomWarning)
            Positioned(
              top: 50,
              left: 16,
              right: 16,
              child: Material(
                elevation: 4,
                borderRadius: BorderRadius.circular(8),
                color: Colors.orange.shade700,
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Row(
                    children: [
                      const Icon(Icons.zoom_in, color: Colors.white),
                      const SizedBox(width: 8),
                      const Expanded(
                        child: Text(
                          'Zoom in to see air quality data',
                          style: TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                      IconButton(
                        icon: const Icon(Icons.close, color: Colors.white),
                        onPressed: () {
                          setState(() => _showZoomWarning = false);
                        },
                      ),
                    ],
                  ),
                ),
              ),
            ),
          if (_isLoading)
            Positioned(
              top: 50,
              right: 16,
              child: Material(
                elevation: 4,
                borderRadius: BorderRadius.circular(8),
                child: const Padding(
                  padding: EdgeInsets.all(12),
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
          Positioned(
            bottom: 100,
            right: 16,
            child: FloatingActionButton(
              heroTag: 'location',
              onPressed: _goToMyLocation,
              child: const Icon(Icons.my_location),
            ),
          ),
          Positioned(
            bottom: 180,
            right: 16,
            child: FloatingActionButton(
              heroTag: 'refresh',
              onPressed: _fetchMapData,
              child: const Icon(Icons.refresh),
            ),
          ),
          const Positioned(
            bottom: 100,
            left: 16,
            child: MapLegend(),
          ),
        ],
      ),
    );
  }
}
