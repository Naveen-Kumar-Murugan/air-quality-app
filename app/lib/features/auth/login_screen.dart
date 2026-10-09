import 'package:flutter/material.dart';
import 'auth_service.dart';
import '../scan/scan_screen.dart';
import '../map/map_screen.dart';
import '../scan/history_screen.dart';
import '../coach/coach_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({Key? key}) : super(key: key);

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final TextEditingController _nameController = TextEditingController();
  bool _isLoading = false;
  bool _isSuccess = false;

  @override
  void dispose() {
    _nameController.dispose();
    super.dispose();
  }

  Future<void> _handleContinue() async {
    setState(() {
      _isLoading = true;
    });

    try {
      final authService = AuthService();
      await authService.signInAsGuest();

      setState(() {
        _isLoading = false;
        _isSuccess = true;
      });

      await Future.delayed(const Duration(milliseconds: 700));

      if (mounted) {
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(builder: (_) => const HomeScreen()),
        );
      }
    } catch (e) {
      setState(() {
        _isLoading = false;
        _isSuccess = false;
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error: $e'),
            backgroundColor: const Color(0xFFBA1A1A),
          ),
        );
      }
    }
  }

  void _setPreset(String name) {
    _nameController.text = name;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF6F9FF), // surface background
      body: SafeArea(
        child: SingleChildScrollView(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16.0),
            child: Column(
              children: [
                const SizedBox(height: 16),
                _buildHeaderCard(),
                const SizedBox(height: 24),
                _buildGuestForm(),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildHeaderCard() {
    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        color: const Color(0xFFFFFFFF),
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            blurRadius: 4,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(12),
        child: Column(
          children: [
            // Atmospheric header image with gradient overlay
            Stack(
              children: [
                Container(
                  height: 176,
                  decoration: const BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [
                        Color(0xFF87CEEB), // Sky blue
                        Color(0xFFE0F4FF),
                      ],
                    ),
                  ),
                ),
                Container(
                  height: 176,
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [
                        Colors.transparent,
                        const Color(0xFFFFFFFF).withOpacity(0.4),
                        const Color(0xFFFFFFFF),
                      ],
                    ),
                  ),
                ),
                // Optics Sensor Active badge
                Positioned(
                  top: 12,
                  right: 12,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: const Color(0xFFFFFFFF).withOpacity(0.9),
                      borderRadius: BorderRadius.circular(20),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withOpacity(0.05),
                          blurRadius: 4,
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
                            color: const Color(0xFF00687A),
                            borderRadius: BorderRadius.circular(4),
                          ),
                        ),
                        const SizedBox(width: 6),
                        const Text(
                          'Optics Sensor Active',
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.w500,
                            color: Color(0xFF0D1D2D),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
            // Brand badge and content
            Transform.translate(
              offset: const Offset(0, -48),
              child: Column(
                children: [
                  // Aperture logo
                  Container(
                    width: 80,
                    height: 80,
                    decoration: BoxDecoration(
                      color: const Color(0xFFFFFFFF),
                      borderRadius: BorderRadius.circular(40),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withOpacity(0.1),
                          blurRadius: 8,
                          offset: const Offset(0, 4),
                        ),
                      ],
                    ),
                    child: Center(
                      child: CustomPaint(
                        size: const Size(56, 56),
                        painter: AperturePainter(),
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  // Skylens title
                  const Text(
                    'Skylens',
                    style: TextStyle(
                      fontFamily: 'Space Grotesk',
                      fontSize: 32,
                      fontWeight: FontWeight.w700,
                      color: Color(0xFF0D1D2D),
                      height: 1.2,
                      letterSpacing: -0.5,
                    ),
                  ),
                  const SizedBox(height: 4),
                  const Text(
                    'Read the air from a photo.',
                    style: TextStyle(
                      fontFamily: 'Space Grotesk',
                      fontSize: 18,
                      fontWeight: FontWeight.w600,
                      color: Color(0xFF0056BB),
                    ),
                  ),
                  const SizedBox(height: 12),
                  const Padding(
                    padding: EdgeInsets.symmetric(horizontal: 32.0),
                    child: Text(
                      'Estimate hyperlocal air quality in seconds with your smartphone camera. Contribute to crowdsourced city air maps.',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 14,
                        color: Color(0xFF424753),
                        height: 1.4,
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildGuestForm() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFFFFFFFF),
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            blurRadius: 4,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 8),
          // Continue button
          SizedBox(
            width: double.infinity,
            height: 52,
            child: ElevatedButton(
              onPressed: _isLoading || _isSuccess ? null : _handleContinue,
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF2A6FDB),
                foregroundColor: const Color(0xFFFFFFFF),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(26),
                ),
                elevation: 2,
                shadowColor: Colors.black.withOpacity(0.1),
              ),
              child: _isLoading
                  ? const Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                          ),
                        ),
                        SizedBox(width: 12),
                        Text(
                          'Initializing optics...',
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    )
                  : _isSuccess
                      ? Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            const Icon(Icons.check_circle, size: 20),
                            const SizedBox(width: 12),
                            Text(
                              'Welcome, ${_nameController.text.isEmpty ? "Guest Observer" : _nameController.text}',
                              style: const TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ],
                        )
                      : const Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Text(
                              'Continue as guest',
                              style: TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            SizedBox(width: 8),
                            Icon(Icons.arrow_forward, size: 20),
                          ],
                        ),
            ),
          ),
          const SizedBox(height: 12),
          const Text(
            'No account needed. Generates an anonymous, ephemeral session.',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 13,
              color: Color(0xFF424753),
              height: 1.4,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildQuickTag(String label) {
    return GestureDetector(
      onTap: () => _setPreset(label),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: const Color(0xFFE4EFFF),
          borderRadius: BorderRadius.circular(20),
        ),
        child: Text(
          label,
          style: const TextStyle(
            fontSize: 12,
            color: Color(0xFF424753),
            fontWeight: FontWeight.w500,
          ),
        ),
      ),
    );
  }
}

// Custom painter for the aperture logo
class AperturePainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..color = const Color(0xFF2A6FDB);

    final center = Offset(size.width / 2, size.height / 2);

    // Outer circle
    paint.strokeWidth = 2.5;
    paint.color = const Color(0xFF2A6FDB).withOpacity(0.3);
    canvas.drawCircle(center, size.width * 0.46, paint);

    // Inner circle
    paint.strokeWidth = 2.0;
    paint.color = const Color(0xFF2A6FDB).withOpacity(0.6);
    canvas.drawCircle(center, size.width * 0.36, paint);

    // Shutter leaves
    paint.strokeWidth = 2.2;
    paint.color = const Color(0xFF2A6FDB);

    final shutterLines = [
      [Offset(center.dx, center.dy - size.height * 0.46), Offset(center.dx + size.width * 0.21, center.dy - size.height * 0.18)],
      [Offset(center.dx + size.width * 0.39, center.dy - size.height * 0.18), Offset(center.dx + size.width * 0.28, center.dy + size.height * 0.14)],
      [Offset(center.dx + size.width * 0.28, center.dy + size.height * 0.21), Offset(center.dx - size.width * 0.04, center.dy + size.height * 0.39)],
      [Offset(center.dx - size.width * 0.25, center.dy + size.height * 0.29), Offset(center.dx - size.width * 0.36, center.dy - size.width * 0.04)],
      [Offset(center.dx - size.width * 0.32, center.dy - size.height * 0.21), Offset(center.dx, center.dy - size.height * 0.39)],
    ];

    for (final line in shutterLines) {
      canvas.drawLine(line[0], line[1], paint);
    }

    // Horizon line
    paint.strokeWidth = 2.8;
    canvas.drawLine(
      Offset(center.dx - size.width * 0.39, center.dy),
      Offset(center.dx + size.width * 0.39, center.dy),
      paint,
    );

    // Center dot
    paint.style = PaintingStyle.fill;
    canvas.drawCircle(center, 4, paint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

// HomeScreen widget (kept from original main.dart)
class HomeScreen extends StatefulWidget {
  const HomeScreen({Key? key}) : super(key: key);

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _currentIndex = 0;

  final List<Widget> _screens = [
    const ScanScreen(),
    const MapScreen(),
    const HistoryScreen(),
    const CoachScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: _screens[_currentIndex],
      bottomNavigationBar: BottomNavigationBar(
        type: BottomNavigationBarType.fixed,
        currentIndex: _currentIndex,
        onTap: (index) => setState(() => _currentIndex = index),
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.camera_alt), label: 'Scan'),
          BottomNavigationBarItem(icon: Icon(Icons.map), label: 'Map'),
          BottomNavigationBarItem(icon: Icon(Icons.history), label: 'History'),
          BottomNavigationBarItem(icon: Icon(Icons.chat), label: 'Coach'),
        ],
      ),
    );
  }
}