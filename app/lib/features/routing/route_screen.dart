import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import '../../core/api_client.dart';
import '../auth/auth_service.dart';
import 'route_service.dart';
import '../map/aqi_colors.dart';

class RouteScreen extends StatefulWidget {
  const RouteScreen({super.key});

  @override
  State<RouteScreen> createState() => _RouteScreenState();
}

class _RouteScreenState extends State<RouteScreen> {
  final MapController _mapController = MapController();
  late final RouteService _routeService;

  LatLng? _origin;
  LatLng? _destination;
  String _mode = 'walking';
  RouteResponse? _routeData;
  bool _isLoading = false;
  RouteOption? _selectedRoute;

  final List<String> _modes = ['walking', 'cycling', 'driving'];
  final List<String> _modeLabels = ['Walking', 'Cycling', 'Driving'];

  @override
  void initState() {
    super.initState();
    final authService = AuthService();
    final apiClient = ApiClient(authService);
    _routeService = RouteService(apiClient);
  }

  Future<void> _fetchRoute() async {
    if (_origin == null || _destination == null) return;
    setState(() => _isLoading = true);
    try {
      final result = await _routeService.fetchRoute(
        originLat: _origin!.latitude,
        originLon: _origin!.longitude,
        destLat: _destination!.latitude,
        destLon: _destination!.longitude,
        mode: _mode,
      );
      setState(() {
        _routeData = result;
        _isLoading = false;
        if (_selectedRoute == null && result.routes.isNotEmpty) {
          _selectedRoute = result.routes.first;
        }
      });
    } catch (_) {
      setState(() => _isLoading = false);
    }
  }

  void _onMapTap(LatLng point) {
    setState(() {
      if (_origin == null) {
        _origin = point;
      } else if (_destination == null) {
        _destination = point;
      } else {
        _destination = point;
      }
    });
  }

  void _onMapLongPress(LatLng point) {
    setState(() {
      if (_destination == null) {
        _destination = point;
      } else {
        _origin = _destination;
        _destination = point;
      }
    });
  }

  Color _segmentColor(double aqi) {
    final category = AQICategoryColors.getCategory(aqi.round());
    return AQICategoryColors.getColor(category);
  }

  List<Polyline> _buildPolylines() {
    final polys = <Polyline>[];
    if (_routeData == null) return polys;
    for (final route in _routeData!.routes) {
      final isSelected = _selectedRoute == route;
      for (final seg in route.segments) {
        final pts = seg.points.map((p) => LatLng(p[0], p[1])).toList();
        if (pts.length < 2) continue;
        polys.add(Polyline(
          points: pts,
          strokeWidth: isSelected ? 7.0 : 5.0,
          color: _segmentColor(seg.aqi),
          strokeCap: StrokeCap.round,
        ));
      }
    }
    return polys;
  }

  Widget _modeButton(String mode, String label) {
    final selected = _mode == mode;
    return ElevatedButton(
      onPressed: () {
        setState(() => _mode = mode);
        if (_origin != null && _destination != null) _fetchRoute();
      },
      style: ElevatedButton.styleFrom(
        backgroundColor: selected ? Theme.of(context).primaryColor : Colors.grey.shade300,
        foregroundColor: selected ? Colors.white : Colors.black87,
      ),
      child: Text(label),
    );
  }

  Widget _card(String title, RouteOption? route) {
    if (route == null) {
      return const SizedBox.shrink();
    }
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 6),
            Row(
              children: [
                Expanded(child: Text('${route.minutes} min')),
                Expanded(child: Text('AQI ${route.avgAqi.toStringAsFixed(0)}')),
                Expanded(child: Text('Exp ${route.exposure.toStringAsFixed(0)}')),
                Expanded(child: Text('Cov ${route.coverage.toStringAsFixed(0)}%')),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _bottomSheet() {
    final fastest = _routeData?.routes.cast<RouteOption?>().firstWhere(
      (r) => r != null && r.label == 'Fastest',
      orElse: () => null,
    );
    final cleanest = _routeData?.routes.cast<RouteOption?>().firstWhere(
      (r) => r != null && r.label == 'Cleanest',
      orElse: () => null,
    );
    final balanced = _routeData?.routes.cast<RouteOption?>().firstWhere(
      (r) => r != null && r.label == 'Balanced',
      orElse: () => null,
    );

    return Container(
      height: 320,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
        boxShadow: [
          BoxShadow(color: Colors.black12, blurRadius: 10, offset: const Offset(0, -2)),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (_routeData != null && _routeData!.routes.isNotEmpty)
            SizedBox(
              height: 40,
              child: ListView(
                scrollDirection: Axis.horizontal,
                children: _routeData!.routes.map((r) {
                  return Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: ChoiceChip(
                      label: Text(r.label),
                      selected: _selectedRoute == r,
                      onSelected: (_) => setState(() => _selectedRoute = r),
                    ),
                  );
                }).toList(),
              ),
            ),
          const SizedBox(height: 8),
          Expanded(
            child: ListView(
              children: [
                _card('Fastest', fastest ?? _routeData?.routes.isNotEmpty == true ? _routeData!.routes.first : null),
                _card('Cleanest', cleanest),
                _card('Balanced', balanced),
              ],
            ),
          ),
          if (_selectedRoute != null && (_selectedRoute!.coverage < 40))
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: Colors.amber.shade50,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: const [
                  Icon(Icons.warning_amber_rounded, color: Colors.amber),
                  SizedBox(width: 8),
                  Expanded(child: Text('Limited local data: estimate leans on nearby stations.')),
                ],
              ),
            ),
          const SizedBox(height: 8),
          ElevatedButton.icon(
            onPressed: _selectedRoute == null
                ? null
                : () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => PlaceholderScreen(
                          title: 'Coach',
                          icon: Icons.chat,
                          routeData: _selectedRoute,
                        ),
                      ),
                    );
                  },
            icon: const Icon(Icons.chat_bubble_outline),
            label: const Text('Ask the coach'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Route'), backgroundColor: Theme.of(context).colorScheme.inversePrimary),
      body: Stack(
        children: [
          FlutterMap(
            mapController: _mapController,
            options: MapOptions(
              center: LatLng(51.5, 0.0),
              zoom: 13.0,
              onTap: (tapPosition, point) => _onMapTap(point),
              onLongPress: (tapPosition, point) => _onMapLongPress(point),
              interactiveFlags: InteractiveFlag.all,
            ),
            children: [
              TileLayer(
                urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                userAgentPackageName: 'com.example.air_quality_app',
              ),
              PolylineLayer(polylines: _buildPolylines()),
              if (_origin != null)
                MarkerLayer(
                  markers: [
                    Marker(
                      point: _origin!,
                      builder: (ctx) => const Icon(Icons.location_on, color: Colors.green, size: 32),
                    ),
                  ],
                ),
              if (_destination != null)
                MarkerLayer(
                  markers: [
                    Marker(
                      point: _destination!,
                      builder: (ctx) => const Icon(Icons.flag, color: Colors.red, size: 32),
                    ),
                  ],
                ),
            ],
          ),
          Positioned(
            top: 12,
            left: 12,
            right: 12,
            child: Row(
              children: [
                Expanded(child: _modeButton('walking', 'Walking')),
                const SizedBox(width: 8),
                Expanded(child: _modeButton('cycling', 'Cycling')),
                const SizedBox(width: 8),
                Expanded(child: _modeButton('driving', 'Driving')),
              ],
            ),
          ),
          Positioned(
            bottom: 0,
            left: 0,
            right: 0,
            child: _bottomSheet(),
          ),
          if (_isLoading)
            const Center(child: CircularProgressIndicator()),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () {
          if (_origin != null && _destination != null) {
            _fetchRoute();
          }
        },
        tooltip: 'Calculate route',
        child: const Icon(Icons.navigation),
      ),
    );
  }
}

class PlaceholderScreen extends StatelessWidget {
  final String title;
  final IconData icon;
  final dynamic routeData;

  const PlaceholderScreen({super.key, required this.title, required this.icon, this.routeData});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 64, color: Colors.grey),
            const SizedBox(height: 16),
            Text('$title - Coming Soon', style: Theme.of(context).textTheme.headlineSmall),
            if (routeData != null) ...[
              const SizedBox(height: 8),
              Text('Route data passed: ${routeData.toString()}', style: Theme.of(context).textTheme.bodySmall),
            ],
          ],
        ),
      ),
    );
  }
}
