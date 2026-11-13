import 'dart:typed_data';
import 'package:flutter/material.dart';
import '../core/api_client.dart';
import '../core/constants.dart';
import '../core/app_theme.dart';
import '../models/diagnosis_result.dart';
import 'assistant_screen.dart';
import 'expert_consultation_screen.dart';

class DiagnosisScreen extends StatefulWidget {
  const DiagnosisScreen({super.key});

  @override
  State<DiagnosisScreen> createState() => _DiagnosisScreenState();
}

class _DiagnosisScreenState extends State<DiagnosisScreen> {
  final ApiClient _api = ApiClient();
  String _selectedCrop = 'all';
  bool _isLoading = false;
  DiagnosisResult? _result;
  String? _errorMessage;
  Uint8List? _previewImage;

  // Generate a test green leaf patch in memory for quick on-device testing
  Uint8List _generateSampleLeafBytes() {
    const int width = 64;
    const int height = 64;
    const int headerSize = 54;
    const int rowSize = (width * 3 + 3) & ~3;
    final int imageSize = rowSize * height;
    final int fileSize = headerSize + imageSize;

    final bytes = Uint8List(fileSize);
    final bd = ByteData.sublistView(bytes);

    // BMP Header
    bytes[0] = 0x42; // 'B'
    bytes[1] = 0x4D; // 'M'
    bd.setUint32(2, fileSize, Endian.little);
    bd.setUint32(10, headerSize, Endian.little);
    bd.setUint32(14, 40, Endian.little); // DIB header size
    bd.setInt32(18, width, Endian.little);
    bd.setInt32(22, height, Endian.little);
    bd.setUint16(26, 1, Endian.little); // planes
    bd.setUint16(28, 24, Endian.little); // 24 bpp
    bd.setUint32(34, imageSize, Endian.little);

    // Fill pixels with lush green shades (BGR)
    for (int y = 0; y < height; y++) {
      final int rowOffset = headerSize + y * rowSize;
      for (int x = 0; x < width; x++) {
        final int px = rowOffset + x * 3;
        bytes[px] = 34;     // Blue
        bytes[px + 1] = 139; // Green
        bytes[px + 2] = 34;  // Red
      }
    }
    return bytes;
  }

  Future<void> _runDiagnosis([Uint8List? customBytes]) async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final bytes = customBytes ?? _generateSampleLeafBytes();
      _previewImage = bytes;
      final cropFilter = _selectedCrop == 'all' ? null : _selectedCrop;

      final res = await _api.predictLeaf(
        imageBytes: bytes,
        filename: 'leaf_capture.jpg',
        cropFilter: cropFilter,
      );

      setState(() {
        _result = res;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _errorMessage = e.toString().replaceAll('Exception: ', '');
        _isLoading = false;
      });
    }
  }

  void _createTaskFromDiagnosis() async {
    if (_result == null) return;
    try {
      final task = await _api.createTask({
        'title': 'Điều trị ${_result!.primaryDisease} (${_result!.crop})',
        'description': 'Biện pháp: ${_result!.organicTreatments.isNotEmpty ? _result!.organicTreatments.first : "Phun thuốc BVTV theo hướng dẫn VietGAP"}',
        'priority': 'HIGH',
        'due_date': DateTime.now().add(const Duration(days: 2)).toIso8601String().split('T').first,
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Đã tạo việc canh tác: ${task?.title ?? "Thành công"}')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Không thể tạo việc: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('GARI Leaf Intelligence'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Chẩn đoán lại',
            onPressed: () => _runDiagnosis(),
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Crop Selector Bar (7 Primary Crops)
            Card(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                child: Row(
                  children: [
                    const Icon(Icons.eco, color: AppTheme.primaryGreen),
                    const SizedBox(width: 12),
                    const Text('Cây trồng: ', style: TextStyle(fontWeight: FontWeight.w600)),
                    const SizedBox(width: 8),
                    Expanded(
                      child: DropdownButtonHideUnderline(
                        child: DropdownButton<String>(
                          value: _selectedCrop,
                          isExpanded: true,
                          items: AppConstants.primaryCrops.map((c) {
                            return DropdownMenuItem(
                              value: c.id,
                              child: Text('${c.icon} ${c.nameVi} (${c.nameEn})'),
                            );
                          }).toList(),
                          onChanged: (val) {
                            if (val != null) setState(() => _selectedCrop = val);
                          },
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            // Camera Viewport & Capture Hero
            Container(
              height: 220,
              decoration: BoxDecoration(
                color: Colors.black87,
                borderRadius: BorderRadius.circular(16),
                image: _previewImage != null
                    ? DecorationImage(image: MemoryImage(_previewImage!), fit: BoxFit.cover)
                    : null,
              ),
              child: Stack(
                alignment: Alignment.center,
                children: [
                  if (_previewImage == null)
                    Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: const [
                        Icon(Icons.camera_alt_outlined, color: Colors.white70, size: 56),
                        SizedBox(height: 8),
                        Text('Hướng camera trực tiếp vào lá bệnh', style: TextStyle(color: Colors.white70)),
                      ],
                    ),
                  if (_isLoading)
                    Container(
                      color: Colors.black54,
                      child: const Center(
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            CircularProgressIndicator(color: AppTheme.primaryLight),
                            SizedBox(height: 12),
                            Text('AI đang phân tích triệu chứng quang học...', style: TextStyle(color: Colors.white)),
                          ],
                        ),
                      ),
                    ),
                ],
              ),
            ),
            const SizedBox(height: 16),

            // Action Buttons
            Row(
              children: [
                Expanded(
                  child: ElevatedButton.icon(
                    icon: const Icon(Icons.camera_alt),
                    label: const Text('Chụp Thực Địa'),
                    onPressed: _isLoading ? null : () => _runDiagnosis(),
                  ),
                ),
                const SizedBox(width: 10),
                OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  ),
                  icon: const Icon(Icons.photo_library),
                  label: const Text('Thư Viện'),
                  onPressed: _isLoading ? null : () => _runDiagnosis(),
                ),
              ],
            ),
            const SizedBox(height: 20),

            // Error Display
            if (_errorMessage != null)
              Card(
                color: const Color(0xFFFEF2F2),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    children: [
                      const Icon(Icons.error_outline, color: AppTheme.accentRed),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(_errorMessage!, style: const TextStyle(color: AppTheme.accentRed)),
                      ),
                    ],
                  ),
                ),
              ),

            // Results Display
            if (_result != null) ...[
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Expanded(
                            child: Text(
                              _result!.primaryDisease,
                              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
                            ),
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                            decoration: BoxDecoration(
                              color: AppTheme.primaryGreen.withAlpha(30),
                              borderRadius: BorderRadius.circular(20),
                            ),
                            child: Text(
                              '${(_result!.confidence * 100).toStringAsFixed(1)}%',
                              style: const TextStyle(
                                color: AppTheme.primaryGreen,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 6),
                      Text(
                        'Cây trồng: ${_result!.crop}',
                        style: const TextStyle(color: Colors.grey, fontSize: 13),
                      ),
                      const Divider(height: 24),

                      // Organic Solutions
                      if (_result!.organicTreatments.isNotEmpty) ...[
                        const Row(
                          children: [
                            Icon(Icons.eco, size: 18, color: AppTheme.primaryGreen),
                            SizedBox(width: 6),
                            Text('Biện pháp Sinh học & Hữu cơ (Khuyên dùng):', style: TextStyle(fontWeight: FontWeight.w600)),
                          ],
                        ),
                        const SizedBox(height: 6),
                        ..._result!.organicTreatments.map((t) => Padding(
                          padding: const EdgeInsets.only(left: 24, bottom: 4),
                          child: Text('• $t', style: const TextStyle(fontSize: 13.5)),
                        )),
                        const SizedBox(height: 12),
                      ],

                      // Chemical / IPM Solutions
                      if (_result!.chemicalTreatments.isNotEmpty) ...[
                        const Row(
                          children: [
                            Icon(Icons.science, size: 18, color: AppTheme.accentAmber),
                            SizedBox(width: 6),
                            Text('Hoạt chất BVTV (Khi mật độ vượt ngưỡng):', style: TextStyle(fontWeight: FontWeight.w600)),
                          ],
                        ),
                        const SizedBox(height: 6),
                        ..._result!.chemicalTreatments.map((t) => Padding(
                          padding: const EdgeInsets.only(left: 24, bottom: 4),
                          child: Text('• $t', style: const TextStyle(fontSize: 13.5)),
                        )),
                      ],
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 14),

              // Connected Actions: Ask AI, Create Task, Consult Expert
              ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.darkGreen,
                ),
                icon: const Icon(Icons.chat),
                label: const Text('Hỏi Trợ Lý AI Về Ca Bệnh Này'),
                onPressed: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => AssistantScreen(
                        initialCrop: _result!.crop,
                        initialDisease: _result!.primaryDisease,
                      ),
                    ),
                  );
                },
              ),
              const SizedBox(height: 8),

              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      icon: const Icon(Icons.add_task),
                      label: const Text('Tạo Việc Trị Bệnh'),
                      onPressed: _createTaskFromDiagnosis,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: OutlinedButton.icon(
                      icon: const Icon(Icons.support_agent),
                      label: const Text('Tư Vấn Chuyên Gia'),
                      onPressed: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => const ExpertConsultationScreen(),
                          ),
                        );
                      },
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}
