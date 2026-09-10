// lib/main.dart
// Exam Corrector Mobile App
//
// Companion app to the Exam Generator web app. A teacher picks the exam
// that was generated on the web app (by its Exam ID), photographs each
// page of a student's completed bubble sheet, and gets an instant score
// with a per-topic breakdown -- graded by the same server that generated
// the exam, so the answer key never has to leave the server.

import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  runApp(const ExamCorrectorApp());
}

class ExamCorrectorApp extends StatelessWidget {
  const ExamCorrectorApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Question Generator - Diagnostic Test 2026/2027',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF1F3A8A),
          brightness: Brightness.light,
        ),
      ),
      home: const HomePage(),
    );
  }
}

class ExamSummary {
  final String examId;
  final String schoolName;
  final String grade;
  final int numQuestions;

  ExamSummary({
    required this.examId,
    required this.schoolName,
    required this.grade,
    required this.numQuestions,
  });

  factory ExamSummary.fromJson(Map<String, dynamic> json) {
    return ExamSummary(
      examId: json['exam_id'],
      schoolName: json['school_name'],
      grade: json['grade'],
      numQuestions: json['num_questions'],
    );
  }

  String get label => '$schoolName - $grade - ${numQuestions}Q ($examId)';
}

class ExamDetail {
  final String examId;
  final String schoolName;
  final String grade;
  final int numQuestions;
  final int numPages;

  ExamDetail({
    required this.examId,
    required this.schoolName,
    required this.grade,
    required this.numQuestions,
    required this.numPages,
  });

  factory ExamDetail.fromJson(Map<String, dynamic> json) {
    return ExamDetail(
      examId: json['exam_id'],
      schoolName: json['school_name'],
      grade: json['grade'],
      numQuestions: json['num_questions'],
      numPages: json['num_pages'],
    );
  }
}

const Map<String, Color> kLevelColors = {
  'Advanced': Color(0xFF10B981),
  'Proficient': Color(0xFF3B82F6),
  'Acceptable': Color(0xFFF59E0B),
  'Needs Support': Color(0xFFEF4444),
};

class HomePage extends StatefulWidget {
  const HomePage({Key? key}) : super(key: key);

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  String serverUrl = 'http://192.168.1.100:5000';
  final serverController = TextEditingController();
  final studentNameController = TextEditingController();

  bool isLoading = false;
  List<ExamSummary> exams = [];
  ExamDetail? selectedExam;
  final Map<int, File> pageImages = {};

  @override
  void initState() {
    super.initState();
    _loadPrefs();
    requestPermissions();
  }

  Future<void> requestPermissions() async {
    await Permission.camera.request();
  }

  Future<void> _loadPrefs() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() {
      serverUrl = prefs.getString('server_url') ?? serverUrl;
      serverController.text = serverUrl;
    });
    refreshExams();
  }

  Future<void> _saveServerUrl() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('server_url', serverUrl);
  }

  void _showSnack(String message, {Color? color}) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: color),
    );
  }

  Future<void> refreshExams() async {
    setState(() => isLoading = true);
    try {
      final res = await http.get(Uri.parse('$serverUrl/api/exams'));
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        setState(() {
          exams = List<ExamSummary>.from(
            (data['exams'] as List).map((e) => ExamSummary.fromJson(e)),
          );
        });
      } else {
        _showSnack('Could not reach server ($serverUrl)', color: Colors.red);
      }
    } catch (e) {
      _showSnack('Network error: $e', color: Colors.red);
    } finally {
      setState(() => isLoading = false);
    }
  }

  Future<void> selectExam(String examId) async {
    setState(() => isLoading = true);
    try {
      final res = await http.get(Uri.parse('$serverUrl/api/exams/$examId'));
      if (res.statusCode == 200) {
        setState(() {
          selectedExam = ExamDetail.fromJson(jsonDecode(res.body));
          pageImages.clear();
        });
      } else {
        _showSnack('Exam not found', color: Colors.orange);
      }
    } catch (e) {
      _showSnack('Network error: $e', color: Colors.red);
    } finally {
      setState(() => isLoading = false);
    }
  }

  Future<void> capturePage(int pageNumber) async {
    try {
      final picker = ImagePicker();
      final pickedFile = await picker.pickImage(
        source: ImageSource.camera,
        maxWidth: 2200,
        imageQuality: 90,
      );
      if (pickedFile != null) {
        setState(() => pageImages[pageNumber] = File(pickedFile.path));
      }
    } catch (e) {
      _showSnack('Camera error: $e', color: Colors.red);
    }
  }

  bool get allPagesCaptured =>
      selectedExam != null &&
      List.generate(selectedExam!.numPages, (i) => i + 1)
          .every((p) => pageImages.containsKey(p));

  Future<void> submitForCorrection() async {
    if (selectedExam == null || !allPagesCaptured) return;

    setState(() => isLoading = true);
    try {
      final request = http.MultipartRequest(
        'POST',
        Uri.parse('$serverUrl/api/exams/${selectedExam!.examId}/correct'),
      );
      request.fields['student_name'] = studentNameController.text;
      for (final entry in pageImages.entries) {
        request.files.add(
          await http.MultipartFile.fromPath('page_${entry.key}', entry.value.path),
        );
      }

      final streamedResponse = await request.send();
      final body = await streamedResponse.stream.bytesToString();

      if (streamedResponse.statusCode == 200) {
        final data = jsonDecode(body);
        if (mounted) showResultDialog(data);
      } else {
        final data = jsonDecode(body);
        _showSnack(data['error'] ?? 'Could not correct this sheet.', color: Colors.red);
      }
    } catch (e) {
      _showSnack('Network error: $e', color: Colors.red);
    } finally {
      setState(() => isLoading = false);
    }
  }

  void showResultDialog(Map<String, dynamic> data) {
    final result = data['result'] as Map<String, dynamic>;
    final level = result['level'] as String;
    final levelColor = kLevelColors[level] ?? Colors.grey;
    final sections = (result['sections'] as Map<String, dynamic>);
    final weakAreas = List<String>.from(result['weak_areas'] ?? []);

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(data['student_name'] ?? 'Result'),
        content: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.blue[50],
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Column(
                  children: [
                    Text(
                      '${result['marks_earned'] ?? result['correct']} / ${result['total_marks'] ?? result['num_questions']}',
                      style: const TextStyle(fontSize: 32, fontWeight: FontWeight.bold, color: Color(0xFF1F3A8A)),
                    ),
                    Text('${result['percentage']}% · ${result['correct']}/${result['num_questions']} questions correct'),
                    const SizedBox(height: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(color: levelColor.withOpacity(0.15), borderRadius: BorderRadius.circular(20)),
                      child: Text(level, style: TextStyle(color: levelColor, fontWeight: FontWeight.bold)),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              const Text('Performance by Topic', style: TextStyle(fontWeight: FontWeight.bold)),
              ...sections.entries.map((e) {
                final s = e.value as Map<String, dynamic>;
                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Text('${s['label']}: ${s['correct']}/${s['total']} (${s['percentage']}%)'),
                );
              }),
              if (weakAreas.isNotEmpty) ...[
                const SizedBox(height: 12),
                const Text('Weak Areas', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.red)),
                Text(weakAreas.join(', ')),
              ],
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              setState(() {
                pageImages.clear();
                studentNameController.clear();
              });
            },
            child: const Text('Correct Another Sheet'),
          ),
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Close')),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Question Generator 2026/2027'),
        backgroundColor: const Color(0xFF1F3A8A),
        foregroundColor: Colors.white,
      ),
      body: Stack(
        children: [
          SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('Server Connection', style: TextStyle(fontWeight: FontWeight.bold)),
                        const SizedBox(height: 8),
                        TextField(
                          controller: serverController,
                          decoration: InputDecoration(
                            hintText: 'Exam Generator server URL',
                            border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                          ),
                          onChanged: (value) => serverUrl = value,
                        ),
                        const SizedBox(height: 8),
                        ElevatedButton.icon(
                          onPressed: () async {
                            setState(() => serverUrl = serverController.text);
                            await _saveServerUrl();
                            refreshExams();
                          },
                          icon: const Icon(Icons.refresh),
                          label: const Text('Connect & Load Exams'),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 16),

                if (exams.isNotEmpty) ...[
                  const Text('Select Exam:', style: TextStyle(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  DropdownButtonFormField<String>(
                    value: selectedExam?.examId,
                    items: exams
                        .map((e) => DropdownMenuItem(value: e.examId, child: Text(e.label, overflow: TextOverflow.ellipsis)))
                        .toList(),
                    onChanged: (examId) {
                      if (examId != null) selectExam(examId);
                    },
                    decoration: InputDecoration(
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                      hintText: 'Choose an exam',
                    ),
                  ),
                ] else if (!isLoading)
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 12),
                    child: Text('No exams found. Generate one on the web app first, then tap "Connect & Load Exams".'),
                  ),

                if (selectedExam != null) ...[
                  const SizedBox(height: 20),
                  Text(
                    '${selectedExam!.schoolName} - ${selectedExam!.grade} - ${selectedExam!.numQuestions} questions',
                    style: const TextStyle(fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: studentNameController,
                    decoration: InputDecoration(
                      labelText: 'Student Name (optional)',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                    ),
                  ),
                  const SizedBox(height: 16),
                  const Text('Capture Answer Sheet Pages:', style: TextStyle(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  ...List.generate(selectedExam!.numPages, (i) => i + 1).map((pageNum) {
                    final captured = pageImages.containsKey(pageNum);
                    return Card(
                      margin: const EdgeInsets.only(bottom: 10),
                      child: ListTile(
                        leading: Icon(
                          captured ? Icons.check_circle : Icons.camera_alt,
                          color: captured ? Colors.green : Colors.grey,
                        ),
                        title: Text('Page $pageNum'),
                        subtitle: captured ? const Text('Captured') : const Text('Not captured yet'),
                        trailing: ElevatedButton(
                          onPressed: () => capturePage(pageNum),
                          child: Text(captured ? 'Retake' : 'Capture'),
                        ),
                      ),
                    );
                  }),
                  const SizedBox(height: 12),
                  ElevatedButton.icon(
                    onPressed: allPagesCaptured ? submitForCorrection : null,
                    icon: const Icon(Icons.check),
                    label: const Text('Correct Sheet'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.green,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                    ),
                  ),
                ],
              ],
            ),
          ),
          if (isLoading)
            Container(
              color: Colors.black.withOpacity(0.4),
              child: const Center(child: CircularProgressIndicator()),
            ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    serverController.dispose();
    studentNameController.dispose();
    super.dispose();
  }
}
