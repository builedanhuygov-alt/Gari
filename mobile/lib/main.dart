import 'package:flutter/material.dart';
import 'core/app_theme.dart';
import 'core/api_client.dart';
import 'screens/diagnosis_screen.dart';
import 'screens/assistant_screen.dart';
import 'screens/expert_consultation_screen.dart';
import 'screens/profile_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await ApiClient().init();
  runApp(const GariMobileApp());
}

class GariMobileApp extends StatelessWidget {
  const GariMobileApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'GARI • Trợ lý nông nghiệp AI',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      home: const MainNavigationShell(),
    );
  }
}

class MainNavigationShell extends StatefulWidget {
  const MainNavigationShell({super.key});

  @override
  State<MainNavigationShell> createState() => _MainNavigationShellState();
}

class _MainNavigationShellState extends State<MainNavigationShell> {
  int _currentIndex = 0;

  final List<Widget> _screens = const [
    DiagnosisScreen(),
    AssistantScreen(),
    ExpertConsultationScreen(),
    ProfileScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: _screens,
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _currentIndex,
        onDestinationSelected: (idx) => setState(() => _currentIndex = idx),
        indicatorColor: AppTheme.lightGreen,
        backgroundColor: Colors.white,
        elevation: 3,
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.center_focus_strong_outlined, color: AppTheme.textMuted),
            selectedIcon: Icon(Icons.center_focus_strong, color: AppTheme.primaryGreen),
            label: 'Chẩn Đoán',
          ),
          NavigationDestination(
            icon: Icon(Icons.chat_bubble_outline, color: AppTheme.textMuted),
            selectedIcon: Icon(Icons.chat_bubble, color: AppTheme.primaryGreen),
            label: 'Hỏi AI',
          ),
          NavigationDestination(
            icon: Icon(Icons.support_agent_outlined, color: AppTheme.textMuted),
            selectedIcon: Icon(Icons.support_agent, color: AppTheme.primaryGreen),
            label: 'Chuyên Gia',
          ),
          NavigationDestination(
            icon: Icon(Icons.person_outline, color: AppTheme.textMuted),
            selectedIcon: Icon(Icons.person, color: AppTheme.primaryGreen),
            label: 'Tài Khoản',
          ),
        ],
      ),
    );
  }
}
