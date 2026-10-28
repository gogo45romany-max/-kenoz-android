// KENOZ — the real interface is the offline Arabic web app in
// ../app/src/main/assets (loaded by com.kenoz.app.MainActivity).
// This Dart entry point only keeps the Flutter toolchain happy.
import 'package:flutter/material.dart';

void main() => runApp(const KenozBootstrap());

class KenozBootstrap extends StatelessWidget {
  const KenozBootstrap({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'كنوز',
      debugShowCheckedModeBanner: false,
      home: const Scaffold(
        backgroundColor: Color(0xFF0F2B46),
        body: Center(
          child: Text(
            'كنوز',
            style: TextStyle(color: Color(0xFFC8A64B), fontSize: 42),
          ),
        ),
      ),
    );
  }
}
