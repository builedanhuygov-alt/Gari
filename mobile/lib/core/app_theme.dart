import 'package:flutter/material.dart';

class AppTheme {
  // GARI Frontend2 Design Identity
  static const Color primaryGreen = Color(0xFF087A43); // Deep Forest Green (#087A43)
  static const Color primaryLight = Color(0xFF10B981); // Emerald Light Accent
  static const Color darkGreen = Color(0xFF064D32);    // Dark Pine Green (#064D32)
  static const Color lightGreen = Color(0xFFE8F6EC);   // Soft Mint Accent (#E8F6EC)
  static const Color surfaceLight = Color(0xFFF5F8F5); // Crisp Light BG (#F5F8F5)
  static const Color textPrimary = Color(0xFF17231C);  // Deep Charcoal (#17231C)
  static const Color textMuted = Color(0xFF6B7A70);    // Sage Muted Grey (#6B7A70)
  static const Color accentAmber = Color(0xFFE9A323);  // Warning Amber (#E9A323)
  static const Color accentRed = Color(0xFFD94B4B);    // Alert Red (#D94B4B)
  static const Color cardLight = Colors.white;

  static ThemeData lightTheme = ThemeData(
    useMaterial3: true,
    colorScheme: ColorScheme.fromSeed(
      seedColor: primaryGreen,
      primary: primaryGreen,
      secondary: darkGreen,
      surface: surfaceLight,
      brightness: Brightness.light,
    ),
    scaffoldBackgroundColor: surfaceLight,
    appBarTheme: const AppBarTheme(
      backgroundColor: cardLight,
      foregroundColor: textPrimary,
      elevation: 0,
      centerTitle: true,
      titleTextStyle: TextStyle(
        fontSize: 18,
        fontWeight: FontWeight.w700,
        color: textPrimary,
      ),
    ),
    cardTheme: CardThemeData(
      color: cardLight,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: const BorderSide(color: Color(0xFFE5E7EB)),
      ),
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: primaryGreen,
        foregroundColor: Colors.white,
        elevation: 0,
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
        textStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: Colors.white,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: Color(0xFFCBD5E1)),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: Color(0xFFE5E7EB)),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: primaryGreen, width: 2),
      ),
    ),
  );
}
