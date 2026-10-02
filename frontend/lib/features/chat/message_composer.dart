import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Shared keyboard behavior for shop messages and AI prompts.
class MessageComposer extends StatefulWidget {
  final TextEditingController controller;
  final VoidCallback onSend;
  final bool enabled;
  final int maxLength;
  final String hint, sendLabel;
  const MessageComposer({
    super.key,
    required this.controller,
    required this.onSend,
    this.enabled = true,
    this.maxLength = 2000,
    this.hint = 'พิมพ์ข้อความ…',
    this.sendLabel = 'ส่งข้อความ',
  });

  @override
  State<MessageComposer> createState() => _MessageComposerState();
}

class _MessageComposerState extends State<MessageComposer> {
  late final FocusNode focus = FocusNode(
    onKeyEvent: (_, event) {
      final enter =
          event.logicalKey == LogicalKeyboardKey.enter ||
          event.logicalKey == LogicalKeyboardKey.numpadEnter;
      final composing = widget.controller.value.composing;
      if (!enter || (composing.isValid && !composing.isCollapsed)) {
        return KeyEventResult.ignored;
      }
      if (event is KeyDownEvent && widget.enabled) {
        if (HardwareKeyboard.instance.isShiftPressed) {
          final value = widget.controller.value;
          final selection = value.selection;
          final start = selection.isValid ? selection.start : value.text.length;
          final end = selection.isValid ? selection.end : value.text.length;
          final text = value.text.replaceRange(start, end, '\n');
          if (text.characters.length <= widget.maxLength) {
            widget.controller.value = TextEditingValue(
              text: text,
              selection: TextSelection.collapsed(offset: start + 1),
            );
          }
        } else {
          _send();
        }
      }
      return KeyEventResult.handled;
    },
  );

  void _send() {
    if (widget.enabled && widget.controller.text.trim().isNotEmpty) {
      widget.onSend();
    }
  }

  @override
  void dispose() {
    focus.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => SafeArea(
    top: false,
    child: Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: TextField(
              controller: widget.controller,
              focusNode: focus,
              enabled: widget.enabled,
              maxLength: widget.maxLength,
              minLines: 1,
              maxLines: 4,
              keyboardType: TextInputType.multiline,
              textInputAction: TextInputAction.newline,
              decoration: InputDecoration(
                hintText: widget.hint,
                helperText: 'Enter ส่ง · Shift+Enter ขึ้นบรรทัดใหม่',
                helperMaxLines: 2,
              ),
            ),
          ),
          const SizedBox(width: 8),
          ValueListenableBuilder<TextEditingValue>(
            valueListenable: widget.controller,
            builder: (_, value, _) => IconButton.filled(
              onPressed: widget.enabled && value.text.trim().isNotEmpty
                  ? _send
                  : null,
              tooltip: widget.sendLabel,
              icon: const Icon(Icons.arrow_upward_rounded),
            ),
          ),
        ],
      ),
    ),
  );
}
