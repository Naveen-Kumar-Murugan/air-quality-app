import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/services.dart' show rootBundle;
import 'package:camera/camera.dart';
import 'package:geolocator/geolocator.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:flutter_image_compress/flutter_image_compress.dart';
import 'package:image_picker/image_picker.dart';
import 'dart:async';
import 'dart:typed_data';
import 'scan_service.dart';
import '../auth/auth_service.dart';
import '../../core/api_client.dart';
import '../../core/demo_config.dart';
import 'result_screen.dart';
import '../map/map_service.dart';

class ScanScreen extends StatefulWidget {
  const ScanScreen({Key? key}) : super(key: key);

  @override
  State<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends State<ScanScreen> with SingleTickerProviderStateMixin {
  CameraController? _cameraController;
  bool _isInitialized = false;
  bool _isProcessing = false;
  String? _errorMessage;
  String? _selectedTag;
  double? _gpsAccuracy;
  Timer? _sensorTimer;
  late AnimationController _pulseController;
  DemoSample? _demoSelectedSample;

  final List<Map<String, dynamic>> _tags = [
    {'label': 'Roadside', 'icon': Icons.traffic},
    {'label': 'Park', 'icon': Icons.park},
    {'label': 'Near construction', 'icon': Icons.construction},
    {'label': 'Residential', 'icon': Icons.home},
    {'label': 'Industrial', 'icon': Icons.factory},
  ];

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    )..repeat();
    if (!DemoConfig.enabled) {
      _initializeCamera();
    } else {
      _isInitialized = true;
      _gpsAccuracy = DemoConfig.accuracyMeters;
    }
    _startSensorUpdates();
  }

  @override
  void dispose() {
    _cameraController?.dispose();
    _sensorTimer?.cancel();
    _pulseController.dispose();
    super.dispose();
  }

  void _startSensorUpdates() {
    if (DemoConfig.enabled) {
      _gpsAccuracy = DemoConfig.accuracyMeters;
      return;
    }
    double? lastAccuracy;
    _sensorTimer = Timer.periodic(const Duration(seconds: 2), (timer) async {
      try {
        final position = await Geolocator.getCurrentPosition(
          desiredAccuracy: LocationAccuracy.high,
          timeLimit: const Duration(seconds: 1),
        );
        if (mounted) {
          if (lastAccuracy == null || (position.accuracy - lastAccuracy!).abs() > 30.0) {
            lastAccuracy = position.accuracy;
            setState(() {
              _gpsAccuracy = position.accuracy;
            });
          }
        }
      } catch (e) {
        // Silently fail for periodic updates
      }
    });
  }

  Future<void> _initializeCamera() async {
    final cameraStatus = await Permission.camera.request();
    final locationStatus = await Permission.location.request();

    if (cameraStatus.isDenied || locationStatus.isDenied) {
      setState(() {
        _errorMessage = 'Camera and location permissions are required';
      });
      return;
    }

    if (cameraStatus.isPermanentlyDenied || locationStatus.isPermanentlyDenied) {
      setState(() {
        _errorMessage = 'Permissions permanently denied. Please enable in settings.';
      });
      return;
    }

    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty) {
        setState(() {
          _errorMessage = 'No camera available';
        });
        return;
      }

      _cameraController = CameraController(
        cameras.first,
        ResolutionPreset.high,
        enableAudio: false,
      );

      await _cameraController!.initialize();
      
      if (mounted) {
        setState(() {
          _isInitialized = true;
        });
      }
    } catch (e) {
      setState(() {
        _errorMessage = 'Failed to initialize camera: $e';
      });
    }
  }

  Future<void> _captureAndUpload() async {
    if (_cameraController == null || !_cameraController!.value.isInitialized) {
      return;
    }

    setState(() {
      _isProcessing = true;
      _errorMessage = null;
    });

    try {
      _showProgressDialog('Getting location...');

      final position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
        timeLimit: const Duration(seconds: 10),
      );

      if (position.accuracy > 50) {
        _showWarningDialog('GPS accuracy is poor (${position.accuracy.toStringAsFixed(0)}m). Results may be less accurate.');
      }

      _updateProgressDialog('Capturing image...');

      final image = await _cameraController!.takePicture();
      final imageBytes = await image.readAsBytes();

      _updateProgressDialog('Compressing image...');

      final compressedBytes = await _compressImage(imageBytes);

      _updateProgressDialog('Getting upload URL...');

      final authService = AuthService();
      final apiClient = ApiClient(authService, longTimeout: true);
      final scanService = ScanService(apiClient);

      final uploadResponse = await scanService.getUploadUrl();

      _updateProgressDialog('Uploading image...');

      await scanService.uploadImage(uploadResponse.uploadUrl, compressedBytes);

      _updateProgressDialog('Processing scan...');

      final submission = ScanSubmission(
        scanId: uploadResponse.scanId,
        s3Key: uploadResponse.s3Key,
        lat: position.latitude,
        lon: position.longitude,
        accuracy: position.accuracy,
        pressure: null,
        tag: _selectedTag,
        timestamp: DateTime.now(),
      );

      final result = await scanService.submitScan(submission);

      Navigator.of(context).pop();

      if (mounted) {
        notifyMapRefresh();
        Navigator.of(context).push(
          MaterialPageRoute(
            builder: (context) => ResultScreen(result: result),
          ),
        );
      }
    } on RateLimitException catch (e) {
      Navigator.of(context).pop();
      _showErrorDialog(e.message);
    } catch (e) {
      Navigator.of(context).pop();
      _showErrorDialog('Failed to process scan: $e');
    } finally {
      if (mounted) {
        setState(() {
          _isProcessing = false;
        });
      }
    }
  }

  Future<void> _captureDemoAndUpload() async {
    if (_isProcessing) return;
    if (_demoSelectedSample == null) {
      _showErrorDialog('Pick a sample sky first.');
      return;
    }

    setState(() {
      _isProcessing = true;
      _errorMessage = null;
    });

    try {
      _showProgressDialog('Loading sample photo...');

      final byteData =
          await rootBundle.load(_demoSelectedSample!.asset);
      final imageBytes = byteData.buffer.asUint8List(
        byteData.offsetInBytes,
        byteData.lengthInBytes,
      );

      _updateProgressDialog('Compressing image...');
      final compressedBytes = await _compressImage(imageBytes);

      _updateProgressDialog('Getting upload URL...');

      final authService = AuthService();
      final apiClient = ApiClient(authService, longTimeout: true);
      final scanService = ScanService(apiClient);

      final uploadResponse = await scanService.getUploadUrl();

      _updateProgressDialog('Uploading image...');

      await scanService.uploadImage(uploadResponse.uploadUrl, compressedBytes);

      _updateProgressDialog('Processing scan...');

      final submission = ScanSubmission(
        scanId: uploadResponse.scanId,
        s3Key: uploadResponse.s3Key,
        lat: DemoConfig.latitude,
        lon: DemoConfig.longitude,
        accuracy: DemoConfig.accuracyMeters,
        pressure: null,
        tag: _selectedTag,
        timestamp: DateTime.now(),
      );

      final result = await scanService.submitScan(submission);

      Navigator.of(context).pop();

      if (mounted) {
        notifyMapRefresh();
        Navigator.of(context).push(
          MaterialPageRoute(
            builder: (context) => ResultScreen(result: result),
          ),
        );
      }
    } on RateLimitException catch (e) {
      Navigator.of(context).pop();
      _showErrorDialog(e.message);
    } catch (e) {
      Navigator.of(context).pop();
      _showErrorDialog('Failed to process scan: $e');
    } finally {
      if (mounted) {
        setState(() {
          _isProcessing = false;
        });
      }
    }
  }

  Future<void> _pickFromGalleryAndUpload() async {
    if (_isProcessing) return;
    
    // Request photos permission
    final photosStatus = await Permission.photos.request();
    if (photosStatus.isDenied) {
      _showErrorDialog('Photos permission is required to select images');
      return;
    }
    if (photosStatus.isPermanentlyDenied) {
      _showErrorDialog('Photos permission permanently denied. Please enable in settings.');
      return;
    }
    
    setState(() {
      _isProcessing = true;
      _errorMessage = null;
    });

    try {
      final picker = ImagePicker();
      final pickedFile = await picker.pickImage(source: ImageSource.gallery);
      if (pickedFile == null) {
        setState(() {
          _isProcessing = false;
        });
        return;
      }

      _showProgressDialog('Getting location...');

      final position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
        timeLimit: const Duration(seconds: 10),
      );

      if (position.accuracy > 50) {
        _showWarningDialog('GPS accuracy is poor (${position.accuracy.toStringAsFixed(0)}m). Results may be less accurate.');
      }

      _updateProgressDialog('Processing image...');

      final imageBytes = await pickedFile.readAsBytes();

      _updateProgressDialog('Compressing image...');

      final compressedBytes = await _compressImage(imageBytes);

      _updateProgressDialog('Getting upload URL...');

      final authService = AuthService();
      final apiClient = ApiClient(authService, longTimeout: true);
      final scanService = ScanService(apiClient);

      final uploadResponse = await scanService.getUploadUrl();

      _updateProgressDialog('Uploading image...');

      await scanService.uploadImage(uploadResponse.uploadUrl, compressedBytes);

      _updateProgressDialog('Processing scan...');

      final submission = ScanSubmission(
        scanId: uploadResponse.scanId,
        s3Key: uploadResponse.s3Key,
        lat: position.latitude,
        lon: position.longitude,
        accuracy: position.accuracy,
        pressure: null,
        tag: _selectedTag,
        timestamp: DateTime.now(),
      );

      final result = await scanService.submitScan(submission);

      Navigator.of(context).pop();

      if (mounted) {
        notifyMapRefresh();
        Navigator.of(context).push(
          MaterialPageRoute(
            builder: (context) => ResultScreen(result: result),
          ),
        );
      }
    } on RateLimitException catch (e) {
      Navigator.of(context).pop();
      _showErrorDialog(e.message);
    } catch (e) {
      Navigator.of(context).pop();
      _showErrorDialog('Failed to process scan: $e');
    } finally {
      if (mounted) {
        setState(() {
          _isProcessing = false;
        });
      }
    }
  }

  Future<Uint8List> _compressImage(Uint8List imageBytes) async {
    if (kIsWeb) {
      // flutter_image_compress has no web implementation; the bundled demo
      // samples are already small, so pass them through unchanged.
      return imageBytes;
    }
    final compressed = await FlutterImageCompress.compressWithList(
      imageBytes,
      minWidth: 512,
      minHeight: 512,
      quality: 85,
      format: CompressFormat.jpeg,
    );
    return Uint8List.fromList(compressed);
  }

  void _showProgressDialog(String message) {
    if (Navigator.of(context).canPop()) {
      Navigator.of(context).pop();
    }
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const CircularProgressIndicator(),
            const SizedBox(height: 16),
            Text(message),
          ],
        ),
      ),
    );
  }

  void _updateProgressDialog(String message) {
    if (Navigator.of(context).canPop()) {
      Navigator.of(context).pop();
    }
    _showProgressDialog(message);
  }

  void _showErrorDialog(String message) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Error'),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  void _showWarningDialog(String message) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Warning'),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Continue Anyway'),
          ),
        ],
      ),
    );
  }

  void _openSettings() async {
    await openAppSettings();
  }

  @override
  Widget build(BuildContext context) {
    if (DemoConfig.enabled) {
      return _buildDemoView();
    }
    if (_errorMessage != null) {
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
              if (_errorMessage!.contains('settings'))
                ElevatedButton.icon(
                  onPressed: _openSettings,
                  icon: const Icon(Icons.settings),
                  label: const Text('Open Settings'),
                ),
              ElevatedButton.icon(
                onPressed: _initializeCamera,
                icon: const Icon(Icons.refresh),
                label: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    if (!_isInitialized || _cameraController == null) {
      return const Center(child: CircularProgressIndicator());
    }

    return Stack(
      children: [
        // Camera preview
        Positioned.fill(
          child: CameraPreview(_cameraController!),
        ),
        
        // Atmospheric gradient overlay
        Positioned.fill(
          child: Container(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [
                  const Color(0xFF0B1B2B).withOpacity(0.6),
                  Colors.transparent,
                  const Color(0xFF0B1B2B).withOpacity(0.85),
                ],
                stops: const [0.0, 0.3, 1.0],
              ),
            ),
          ),
        ),

        // Main content
        SafeArea(
          child: Column(
            children: [
              // Top telemetry pills
              _buildTopTelemetry(),
              
              // Center reticle
              Expanded(
                child: Center(
                  child: _buildReticle(),
                ),
              ),
              
              // Bottom controls
              _buildBottomControls(),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildDemoView() {
    final sample = _demoSelectedSample;
    return Stack(
      children: [
        Positioned.fill(
          child: sample == null
              ? Container(
                  decoration: const BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [Color(0xFF2A6FDB), Color(0xFF0B1B2B)],
                    ),
                  ),
                )
              : Image.asset(
                  sample.asset,
                  fit: BoxFit.cover,
                  color: const Color(0xFF0B1B2B).withOpacity(0.25),
                  colorBlendMode: BlendMode.darken,
                ),
        ),
        Positioned.fill(
          child: Container(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [
                  const Color(0xFF0B1B2B).withOpacity(0.55),
                  Colors.transparent,
                  const Color(0xFF0B1B2B).withOpacity(0.9),
                ],
                stops: const [0.0, 0.35, 1.0],
              ),
            ),
          ),
        ),
        SafeArea(
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.only(top: 12),
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: const Color(0xFFFFB68C),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: const Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.science, size: 14, color: Color(0xFF321200)),
                      SizedBox(width: 6),
                      Text(
                        'Demo mode • sample skies',
                        style: TextStyle(
                          color: Color(0xFF321200),
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 12),
              _buildTopTelemetry(),
              const Spacer(),
              _buildDemoControls(),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildDemoControls() {
    final sample = _demoSelectedSample;
    return Padding(
      padding: const EdgeInsets.only(left: 16, right: 16, bottom: 24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: const Color(0xFF0B1B2B).withOpacity(0.65),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Row(
              children: [
                Icon(
                  sample?.icon ?? Icons.touch_app,
                  size: 18,
                  color: const Color(0xFF22C7E8),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    sample == null
                        ? 'Pick a sample sky below'
                        : '${sample.label}  •  typical ${sample.aqiHint}',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 13,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          _buildDemoSampleRow(),
          const SizedBox(height: 14),
          _buildDemoShutterButton(),
          const SizedBox(height: 4),
          const Text(
            'Tap to run the real scan pipeline',
            style: TextStyle(color: Colors.white70, fontSize: 12),
          ),
        ],
      ),
    );
  }

  Widget _buildDemoSampleRow() {
    final selected = _demoSelectedSample;
    return SizedBox(
      height: 76,
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        itemCount: DemoConfig.samples.length,
        itemBuilder: (context, index) {
          final s = DemoConfig.samples[index];
          final isSelected = selected?.asset == s.asset;
          return GestureDetector(
            onTap: () => setState(() => _demoSelectedSample = s),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 180),
              margin: const EdgeInsets.only(right: 10),
              width: 96,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(14),
                border: Border.all(
                  color: isSelected ? const Color(0xFF22C7E8) : Colors.white24,
                  width: isSelected ? 3 : 1,
                ),
                boxShadow: isSelected
                    ? [
                        BoxShadow(
                          color: const Color(0xFF22C7E8).withOpacity(0.4),
                          blurRadius: 12,
                          spreadRadius: 1,
                        )
                      ]
                    : null,
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(11),
                child: Stack(
                  fit: StackFit.expand,
                  children: [
                    Image.asset(s.asset, fit: BoxFit.cover),
                    Positioned(
                      left: 0,
                      right: 0,
                      bottom: 0,
                      child: Container(
                        padding: const EdgeInsets.symmetric(vertical: 3),
                        color: Colors.black54,
                        child: Text(
                          s.label,
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 10,
                            fontWeight: FontWeight.w600,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildDemoShutterButton() {
    return GestureDetector(
      onTap: _isProcessing ? null : _captureDemoAndUpload,
      child: Container(
        width: 88,
        height: 88,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          boxShadow: [
            BoxShadow(
              color: const Color(0xFF22C7E8).withOpacity(0.35),
              blurRadius: 24,
              spreadRadius: 4,
            ),
          ],
        ),
        child: Container(
          padding: const EdgeInsets.all(4),
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.3),
            shape: BoxShape.circle,
          ),
          child: Container(
            decoration: const BoxDecoration(
              color: Color(0xFF2A6FDB),
              shape: BoxShape.circle,
            ),
            child: Container(
              margin: const EdgeInsets.all(9),
              decoration: const BoxDecoration(
                color: Color(0xFFF6F9FC),
                shape: BoxShape.circle,
              ),
              child: _isProcessing
                  ? const Center(
                      child: SizedBox(
                        width: 24,
                        height: 24,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Color(0xFF2A6FDB),
                        ),
                      ),
                    )
                  : const Icon(
                      Icons.camera_alt,
                      color: Color(0xFF2A6FDB),
                      size: 28,
                    ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildTopTelemetry() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          // GPS pill
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: const Color(0xFF0B1B2B).withOpacity(0.75),
              borderRadius: BorderRadius.circular(20),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.3),
                  blurRadius: 8,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                FadeTransition(
                  opacity: _pulseController,
                  child: Container(
                    width: 8,
                    height: 8,
                    decoration: const BoxDecoration(
                      color: Color(0xFF22C7E8),
                      shape: BoxShape.circle,
                    ),
                  ),
                ),
                const SizedBox(width: 6),
                const Icon(
                  Icons.my_location,
                  size: 14,
                  color: Color(0xFF22C7E8),
                ),
                const SizedBox(width: 6),
                Text(
                  'GPS: ±${_gpsAccuracy?.toStringAsFixed(0) ?? '—'}m',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 12,
                    fontWeight: FontWeight.w500,
                    letterSpacing: 0.5,
                  ),
                ),
              ],
            ),
          ),
          
          // Exposure and pressure pills
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                decoration: BoxDecoration(
                  color: const Color(0xFF0B1B2B).withOpacity(0.6),
                  borderRadius: BorderRadius.circular(20),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withOpacity(0.3),
                      blurRadius: 8,
                      offset: const Offset(0, 2),
                    ),
                  ],
                ),
                child: const Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      Icons.wb_sunny,
                      size: 14,
                      color: Color(0xFF22C7E8),
                    ),
                    SizedBox(width: 4),
                    Text(
                      'EV +0.2',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 11,
                        fontWeight: FontWeight.w400,
                        fontFeatures: [FontFeature.tabularFigures()],
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: const Color(0xFF0B1B2B).withOpacity(0.75),
                  borderRadius: BorderRadius.circular(20),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withOpacity(0.3),
                      blurRadius: 8,
                      offset: const Offset(0, 2),
                    ),
                  ],
                ),
                child: const Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      Icons.speed,
                      size: 15,
                      color: Color(0xFF22C7E8),
                    ),
                    SizedBox(width: 6),
                    Text(
                      '1014 hPa',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 12,
                        fontWeight: FontWeight.w500,
                        letterSpacing: 0.5,
                      ),
                    ),
                    SizedBox(width: 4),
                    Icon(
                      Icons.trending_flat,
                      size: 12,
                      color: Color(0xFF22C7E8),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildReticle() {
    return SizedBox(
      width: 256,
      height: 256,
      child: Stack(
        children: [
          // Corner brackets
          Positioned(
            top: 0,
            left: 0,
            child: Container(
              width: 24,
              height: 24,
              decoration: const BoxDecoration(
                border: Border(
                  top: BorderSide(color: Color(0xFF22C7E8), width: 2),
                  left: BorderSide(color: Color(0xFF22C7E8), width: 2),
                ),
              ),
            ),
          ),
          Positioned(
            top: 0,
            right: 0,
            child: Container(
              width: 24,
              height: 24,
              decoration: const BoxDecoration(
                border: Border(
                  top: BorderSide(color: Color(0xFF22C7E8), width: 2),
                  right: BorderSide(color: Color(0xFF22C7E8), width: 2),
                ),
              ),
            ),
          ),
          Positioned(
            bottom: 0,
            left: 0,
            child: Container(
              width: 24,
              height: 24,
              decoration: const BoxDecoration(
                border: Border(
                  bottom: BorderSide(color: Color(0xFF22C7E8), width: 2),
                  left: BorderSide(color: Color(0xFF22C7E8), width: 2),
                ),
              ),
            ),
          ),
          Positioned(
            bottom: 0,
            right: 0,
            child: Container(
              width: 24,
              height: 24,
              decoration: const BoxDecoration(
                border: Border(
                  bottom: BorderSide(color: Color(0xFF22C7E8), width: 2),
                  right: BorderSide(color: Color(0xFF22C7E8), width: 2),
                ),
              ),
            ),
          ),
          
          // Horizon line with crosshair
          Center(
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Container(
                  width: 80,
                  height: 1.5,
                  color: const Color(0xFF22C7E8).withOpacity(0.6),
                ),
                const SizedBox(width: 8),
                Container(
                  width: 12,
                  height: 12,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: const Color(0xFF22C7E8).withOpacity(0.8),
                      width: 1,
                    ),
                  ),
                  child: Center(
                    child: Container(
                      width: 4,
                      height: 4,
                      decoration: const BoxDecoration(
                        color: Color(0xFF22C7E8),
                        shape: BoxShape.circle,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Container(
                  width: 80,
                  height: 1.5,
                  color: const Color(0xFF22C7E8).withOpacity(0.6),
                ),
              ],
            ),
          ),
          
          // Vertical reference lines
          Positioned(
            top: 12,
            left: 128,
            child: Container(
              width: 1.5,
              height: 40,
              color: const Color(0xFF22C7E8).withOpacity(0.4),
            ),
          ),
          Positioned(
            bottom: 12,
            left: 128,
            child: Container(
              width: 1.5,
              height: 40,
              color: const Color(0xFF22C7E8).withOpacity(0.4),
            ),
          ),
          
          // Optical guidance badge
          Positioned(
            top: 24,
            left: 0,
            right: 0,
            child: Center(
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: const Color(0xFF0B1B2B).withOpacity(0.8),
                  borderRadius: BorderRadius.circular(20),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withOpacity(0.3),
                      blurRadius: 12,
                      offset: const Offset(0, 2),
                    ),
                  ],
                ),
                child: const Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      Icons.photo_size_select_small,
                      size: 14,
                      color: Color(0xFF22C7E8),
                    ),
                    SizedBox(width: 6),
                    Text(
                      'Include sky & distant horizon',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 12,
                        fontWeight: FontWeight.w400,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          
          // Solar azimuth badge
          Positioned(
            bottom: -32,
            left: 0,
            right: 0,
            child: Center(
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: const Color(0xFF0B1B2B).withOpacity(0.75),
                  borderRadius: BorderRadius.circular(20),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withOpacity(0.2),
                      blurRadius: 8,
                      offset: const Offset(0, 2),
                    ),
                  ],
                ),
                child: const Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      Icons.light_mode,
                      size: 13,
                      color: Color(0xFFFFB68C),
                    ),
                    SizedBox(width: 6),
                    Text(
                      'AZ: 142° • ELEV: 38°',
                      style: TextStyle(
                        color: Color(0xFFE4EFFF),
                        fontSize: 11,
                        fontWeight: FontWeight.w400,
                        fontFeatures: [FontFeature.tabularFigures()],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBottomControls() {
    return Padding(
      padding: const EdgeInsets.only(left: 16, right: 16, bottom: 24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Context tags row
          SizedBox(
            height: 38,
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              itemCount: _tags.length,
              itemBuilder: (context, index) {
                final tag = _tags[index];
                final isSelected = _selectedTag == tag['label'];
                return Padding(
                  padding: EdgeInsets.only(right: index < _tags.length - 1 ? 8 : 0),
                  child: _buildContextTag(
                    tag['label'] as String,
                    tag['icon'] as IconData,
                    isSelected,
                  ),
                );
              },
            ),
          ),
          
          const SizedBox(height: 16),
          
          // Shutter button row
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              // Gallery thumbnail placeholder
              GestureDetector(
                onTap: _isProcessing ? null : _pickFromGalleryAndUpload,
                child: Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    color: const Color(0xFFD4E4FA),
                    borderRadius: BorderRadius.circular(12),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withOpacity(0.2),
                        blurRadius: 8,
                        offset: const Offset(0, 2),
                      ),
                    ],
                  ),
                  child: const Icon(
                    Icons.photo_library,
                    color: Color(0xFF2A6FDB),
                    size: 24,
                  ),
                ),
              ),
              
              // Shutter button
              _buildShutterButton(),

              // Spacer to balance gallery button on left
              const SizedBox(width: 48),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildContextTag(String label, IconData icon, bool isSelected) {
    return GestureDetector(
      onTap: () {
        setState(() {
          _selectedTag = isSelected ? null : label;
        });
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        decoration: BoxDecoration(
          color: isSelected 
              ? const Color(0xFFF6F9FC) 
              : const Color(0xFFF6F9FC).withOpacity(0.8),
          borderRadius: BorderRadius.circular(19),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(isSelected ? 0.25 : 0.15),
              blurRadius: isSelected ? 12 : 8,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              size: 16,
              color: isSelected ? const Color(0xFF2A6FDB) : const Color(0xFF424753),
            ),
            const SizedBox(width: 6),
            Text(
              label,
              style: TextStyle(
                color: isSelected ? const Color(0xFF2A6FDB) : const Color(0xFF0D1D2D),
                fontSize: 13,
                fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
              ),
            ),
            if (isSelected) ...[
              const SizedBox(width: 4),
              const Icon(
                Icons.check,
                size: 14,
                color: Color(0xFF2A6FDB),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildShutterButton() {
    return GestureDetector(
      onTap: _isProcessing ? null : _captureAndUpload,
      child: Container(
        width: 88,
        height: 88,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          boxShadow: [
            BoxShadow(
              color: const Color(0xFF2A6FDB).withOpacity(0.2),
              blurRadius: 24,
              spreadRadius: 4,
            ),
          ],
        ),
        child: Container(
          padding: const EdgeInsets.all(4),
          decoration: BoxDecoration(
            color: const Color(0xFFF6F9FC).withOpacity(0.3),
            shape: BoxShape.circle,
          ),
          child: Container(
            decoration: const BoxDecoration(
              color: Color(0xFF2A6FDB),
              shape: BoxShape.circle,
              boxShadow: [
                BoxShadow(
                  color: Colors.black26,
                  blurRadius: 8,
                  offset: Offset(0, 2),
                ),
              ],
            ),
            child: Container(
              margin: const EdgeInsets.all(9),
              decoration: const BoxDecoration(
                color: Color(0xFFF6F9FC),
                shape: BoxShape.circle,
                boxShadow: [
                  BoxShadow(
                    color: Colors.black12,
                    blurRadius: 4,
                    offset: Offset(0, 2),
                  ),
                ],
              ),
              child: _isProcessing
                  ? const Center(
                      child: SizedBox(
                        width: 24,
                        height: 24,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Color(0xFF2A6FDB),
                        ),
                      ),
                    )
                  : const Icon(
                      Icons.camera_alt,
                      color: Color(0xFF2A6FDB),
                      size: 28,
                    ),
            ),
          ),
        ),
      ),
    );
  }
}
