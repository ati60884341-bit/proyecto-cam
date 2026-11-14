import 'package:flutter/material.dart';
import '../api_client.dart';
import '../theme.dart';
import '../widgets/mjpeg_view.dart';

class LiveCameraScreen extends StatelessWidget {
  final ApiClient api;
  final Camara camara;
  const LiveCameraScreen({super.key, required this.api, required this.camara});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(backgroundColor: AppColors.panel, title: Text(camara.nombre)),
      body: Center(child: MjpegView(uri: api.streamUri(camara.zona), headers: api.authHeaders)),
    );
  }
}
