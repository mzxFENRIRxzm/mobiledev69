import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'messages_test.dart' show ChatApi, mountChat;
import 'ai_chat_test.dart' show FakeAiApi, mount;

class PagedChatApi extends ChatApi {
  @override
  Future<dynamic> request(
    String path, {
    String method = 'GET',
    Object? data,
  }) async {
    final uri = Uri.parse(path);
    if (uri.path == 'conversations/1/messages/' && method == 'GET') {
      final before = uri.queryParameters['before'];
      final after = uri.queryParameters['after'];
      final id = before != null
          ? 1
          : after == null
          ? 2
          : 3;
      return {
        'results': after == '3'
            ? []
            : [
                {
                  'id': id,
                  'sender_name': 'mechanic',
                  'body': ['older', 'recent', 'newer'][id - 1],
                },
              ],
        'has_more': before == null && after == null,
      };
    }
    return super.request(path, method: method, data: data);
  }
}

class PagedAiApi extends FakeAiApi {
  @override
  Future<dynamic> request(
    String path, {
    String method = 'GET',
    Object? data,
  }) async {
    final uri = Uri.parse(path);
    if (uri.path == 'ai-conversations/room/') {
      final older = uri.queryParameters.containsKey('before');
      return {
        'has_more': !older,
        'turns': [
          {
            'id': older ? 1 : 2,
            'message': older ? 'old question' : 'new question',
            'reply': 'test answer',
            'status': 'completed',
            'sources': [],
          },
        ],
      };
    }
    return super.request(path, method: method, data: data);
  }
}

void main() {
  testWidgets('older shop messages survive polling and new arrivals', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1440, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await mountChat(tester, PagedChatApi());
    await tester.tap(find.text('Shop One'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('โหลดข้อความก่อนหน้า'));
    await tester.pumpAndSettle();
    expect(find.text('older'), findsOneWidget);
    await tester.pump(const Duration(seconds: 5));
    await tester.pumpAndSettle();
    expect(find.text('older'), findsOneWidget);
    expect(find.text('newer'), findsOneWidget);
    expect(find.text('โหลดข้อความก่อนหน้า'), findsNothing);
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('AI older page merges with the latest history', (tester) async {
    await mount(tester, PagedAiApi());
    await tester.tap(find.text('โหลดข้อความก่อนหน้า'));
    await tester.pumpAndSettle();
    expect(find.text('old question'), findsOneWidget);
    expect(find.text('new question'), findsOneWidget);
    expect(find.text('โหลดข้อความก่อนหน้า'), findsNothing);
    await tester.pumpWidget(const SizedBox());
  });
}
