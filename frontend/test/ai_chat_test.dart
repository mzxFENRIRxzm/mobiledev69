import 'dart:async';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:the_x/core/api/api_service.dart';
import 'package:the_x/core/auth/auth_service.dart';
import 'package:the_x/features/auth/auth_repository.dart';
import 'package:the_x/features/auth/auth_view_model.dart';
import 'package:the_x/features/chat/ai_chat_screen.dart';

class FakeAiApi extends ApiService {
  FakeAiApi() : super(AuthService(const FlutterSecureStorage()));
  int posts = 0;
  final completion = Completer<dynamic>();
  final history = <Map<String, dynamic>>[];
  Map<String, dynamic>? sent;

  @override
  Future<dynamic> request(
    String path, {
    String method = 'GET',
    Object? data,
  }) async {
    path = path.split('?').first;
    if (path == 'ai-conversations/') {
      if (method == 'POST') return {'id': 'room', 'title': 'บทสนทนาใหม่'};
      return [
        {'id': 'room', 'title': 'Saved conversation'},
      ];
    }
    if (path == 'ai-conversations/room/') return {'turns': history};
    posts++;
    sent = Map<String, dynamic>.from(data as Map);
    return completion.future;
  }
}

Future<void> mount(WidgetTester tester, FakeAiApi api) async {
  final auth = AuthViewModel(AuthRepository(api.auth, api))
    ..user = const AppUser('customer', 'customer')
    ..loading = false;
  await tester.pumpWidget(
    MultiProvider(
      providers: [
        Provider<ApiService>.value(value: api),
        ChangeNotifierProvider<AuthViewModel>.value(value: auth),
      ],
      child: const MaterialApp(home: AiChatScreen()),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets(
    'restores saved history and shows only server-provided citations',
    (tester) async {
      final api = FakeAiApi();
      api.history.add({
        'message': 'Old question',
        'reply': 'Saved answer',
        'status': 'completed',
        'sources': <dynamic>[],
      });
      await mount(tester, api);
      expect(find.text('Saved answer'), findsOneWidget);
      expect(
        find.text('ข้อมูลทั่วไป — ไม่มีคู่มืออ้างอิงในคำตอบนี้'),
        findsOneWidget,
      );
      await tester.pumpWidget(const SizedBox());
    },
  );

  testWidgets('double click sends once and failure keeps typed question', (
    tester,
  ) async {
    final api = FakeAiApi();
    await mount(tester, api);
    await tester.enterText(find.byType(TextField), 'สตาร์ตยาก');
    await tester.tap(find.byTooltip('ส่งคำถาม'));
    await tester.pump();
    await tester.tap(find.byTooltip('ส่งคำถาม'));
    expect(api.posts, 1);
    expect(api.sent!['conversation_id'], 'room');
    expect(api.sent!['request_id'], matches(RegExp(r'^[a-f0-9-]{36}$')));
    api.completion.completeError(
      DioException(
        requestOptions: RequestOptions(path: 'ai-chat/'),
        response: Response(
          requestOptions: RequestOptions(path: 'ai-chat/'),
          statusCode: 503,
          data: {'detail': 'AI unavailable'},
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('AI unavailable'), findsOneWidget);
    expect(find.text('สตาร์ตยาก'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('leaving during an AI request does not update disposed widget', (
    tester,
  ) async {
    final api = FakeAiApi();
    await mount(tester, api);
    await tester.enterText(find.byType(TextField), 'Question');
    await tester.tap(find.byTooltip('ส่งคำถาม'));
    await tester.pump();
    await tester.pumpWidget(const SizedBox());
    api.completion.complete({'reply': 'Late'});
    await tester.pump();
    expect(tester.takeException(), isNull);
  });
}
