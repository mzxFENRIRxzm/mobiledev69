import 'dart:async';
import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/rendering.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:the_x/core/api/api_service.dart';
import 'package:the_x/core/ui/app_theme.dart';
import 'package:the_x/features/auth/auth_repository.dart';
import 'package:the_x/features/auth/auth_view_model.dart';
import 'package:the_x/features/chat/chat_screen.dart';
import 'package:the_x/features/chat/message_composer.dart';
import 'package:the_x/features/notifications/notification_store.dart';
import 'ai_chat_test.dart' show FakeAiApi;

class ChatApi extends FakeAiApi {
  int sends = 0;
  final sentIds = <String>[];
  bool fail = false;
  final roomOne = Completer<dynamic>();
  bool holdRoomOne = false;
  @override
  Future<dynamic> request(
    String path, {
    String method = 'GET',
    Object? data,
  }) async {
    path = path.split('?').first;
    if (path == 'conversations/') {
      return [
        {
          'id': 1,
          'shop_name': 'Shop One',
          'customer_name': 'customer',
          'unread_count': 1,
          'last_message': 'Hello',
        },
        {
          'id': 2,
          'shop_name': 'Shop Two',
          'customer_name': 'customer',
          'unread_count': 0,
        },
      ];
    }
    if (path.endsWith('/read/')) return {'ok': true};
    if (method == 'POST') {
      sends++;
      sentIds.add((data as Map)['request_id'] as String);
      if (fail) throw Exception('offline');
      return {'id': 3};
    }
    if (path == 'conversations/1/messages/' && holdRoomOne) {
      return roomOne.future;
    }
    return [
      {
        'id': 2,
        'sender_name': 'mechanic',
        'body': 'Reply for $path',
        'created_at': '2026-09-27T12:00:00Z',
      },
    ];
  }
}

Future<void> mountChat(WidgetTester tester, ChatApi api) async {
  final auth = AuthViewModel(AuthRepository(api.auth, api))
    ..user = const AppUser('customer', 'customer')
    ..loading = false;
  await tester.pumpWidget(
    MultiProvider(
      providers: [
        Provider<ApiService>.value(value: api),
        ChangeNotifierProvider.value(value: auth),
      ],
      child: MaterialApp(theme: buildAppTheme(), home: const MessagesScreen()),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  for (final width in [390.0, 1440.0]) {
    testWidgets('chat and notification panel layout at $width', (tester) async {
      tester.view.physicalSize = Size(width, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.runAsync(() async {
        await (FontLoader(
          'NotoSansThai',
        )..addFont(rootBundle.load('assets/fonts/NotoSansThai.ttf'))).load();
        await (FontLoader(
          'MaterialIcons',
        )..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'))).load();
      });
      final api = ChatApi();
      final auth = AuthViewModel(AuthRepository(api.auth, api))
        ..user = const AppUser('customer', 'customer')
        ..loading = false;
      final inbox = NotificationStore(api)
        ..unread = 2
        ..items = [
          {
            'id': 1,
            'title': 'ข้อความใหม่ · ร้านตัวอย่าง',
            'conversation': 1,
            'read_at': null,
            'created_at': '2026-09-27T12:00:00Z',
          },
          {
            'id': 2,
            'title': 'การจอง #12 · รับงานแล้ว',
            'booking': 12,
            'read_at': null,
            'created_at': '2026-09-27T12:00:00Z',
          },
        ];
      final boundary = GlobalKey();
      await tester.pumpWidget(
        MultiProvider(
          providers: [
            Provider<ApiService>.value(value: api),
            ChangeNotifierProvider.value(value: auth),
            ChangeNotifierProvider.value(value: inbox),
          ],
          child: RepaintBoundary(
            key: boundary,
            child: MaterialApp(
              theme: buildAppTheme(),
              home: const MessagesScreen(),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Shop One'));
      await tester.pumpAndSettle();
      Future<void> capture(String name) async {
        if (!const bool.fromEnvironment('UI_PREVIEWS')) return;
        await tester.runAsync(() async {
          final render =
              boundary.currentContext!.findRenderObject()!
                  as RenderRepaintBoundary;
          final image = await render.toImage();
          final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
          final file = File('../.local/$name-${width.toInt()}.png');
          await file.parent.create(recursive: true);
          await file.writeAsBytes(bytes!.buffer.asUint8List());
          image.dispose();
        });
      }

      await capture('messages');
      await tester.tap(find.byTooltip('การแจ้งเตือน (2 ยังไม่อ่าน)'));
      await tester.pumpAndSettle();
      expect(find.text('ข้อความใหม่ · ร้านตัวอย่าง'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await capture('notifications');
      await tester.pumpWidget(const SizedBox());
      inbox.dispose();
      auth.dispose();
    });
  }
  testWidgets(
    'Enter sends once; Shift Enter inserts newline; composing Enter does not send',
    (tester) async {
      final input = TextEditingController();
      var sent = 0;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: MessageComposer(controller: input, onSend: () => sent++),
          ),
        ),
      );
      await tester.enterText(find.byType(TextField), 'Hello');
      await tester.sendKeyEvent(LogicalKeyboardKey.enter);
      expect(sent, 1);
      await tester.sendKeyDownEvent(LogicalKeyboardKey.shiftLeft);
      await tester.sendKeyEvent(LogicalKeyboardKey.enter);
      await tester.sendKeyUpEvent(LogicalKeyboardKey.shiftLeft);
      expect(sent, 1);
      expect(input.text, contains('\n'));
      input.value = const TextEditingValue(
        text: 'compose',
        selection: TextSelection.collapsed(offset: 7),
        composing: TextRange(start: 0, end: 7),
      );
      await tester.sendKeyEvent(LogicalKeyboardKey.enter);
      expect(sent, 1);
      await tester.pumpWidget(const SizedBox());
      input.dispose();
    },
  );

  testWidgets(
    'mobile chat keeps failed draft and Enter sends, with return to inbox',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = ChatApi()..fail = true;
      await mountChat(tester, api);
      await tester.tap(find.text('Shop One'));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField), 'Keep my draft');
      await tester.sendKeyEvent(LogicalKeyboardKey.enter);
      await tester.pumpAndSettle();
      expect(api.sends, 1);
      expect(find.text('Keep my draft'), findsOneWidget);
      api.fail = false;
      await tester.sendKeyEvent(LogicalKeyboardKey.enter);
      await tester.pumpAndSettle();
      expect(api.sends, 2);
      expect(api.sentIds[0], api.sentIds[1]);
      expect(find.text('Keep my draft'), findsNothing);
      await tester.tap(find.byTooltip('กลับกล่องข้อความ'));
      await tester.pumpAndSettle();
      expect(find.text('Shop Two'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
    },
  );

  testWidgets(
    'late result from previous room never replaces selected conversation',
    (tester) async {
      tester.view.physicalSize = const Size(1440, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = ChatApi()..holdRoomOne = true;
      await mountChat(tester, api);
      await tester.tap(find.text('Shop One'));
      await tester.pump();
      await tester.tap(find.text('Shop Two'));
      await tester.pumpAndSettle();
      api.roomOne.complete([
        {'id': 1, 'sender_name': 'mechanic', 'body': 'WRONG ROOM'},
      ]);
      await tester.pumpAndSettle();
      expect(find.text('WRONG ROOM'), findsNothing);
      expect(find.text('Reply for conversations/2/messages/'), findsOneWidget);
      await tester.pumpWidget(const SizedBox());
    },
  );

  testWidgets(
    'notification store discards account A response after switching to B',
    (tester) async {
      final api = InboxApi();
      final store = NotificationStore(api);
      store.setAccount('a');
      store.setAccount('b');
      api.requests[1].complete({
        'results': [],
        'unread_count': 0,
        'latest_id': 0,
      });
      await tester.pump();
      api.requests[0].complete({
        'results': [
          {'id': 1, 'title': 'private'},
        ],
        'unread_count': 1,
        'latest_id': 1,
      });
      await tester.pump();
      expect(store.items, isEmpty);
      expect(store.unread, 0);
      final load = store.refresh();
      api.requests[2].complete({
        'results': [
          {'id': 2, 'read_at': null},
        ],
        'unread_count': 1,
        'latest_id': 2,
      });
      await load;
      expect(store.announcement, 1);
      expect(store.unread, 1);
      store.setAccount(null);
      expect(store.items, isEmpty);
      store.dispose();
    },
  );
}

class InboxApi extends FakeAiApi {
  final requests = <Completer<dynamic>>[];
  @override
  Future<dynamic> request(String path, {String method = 'GET', Object? data}) {
    final result = Completer<dynamic>();
    requests.add(result);
    return result.future;
  }
}
