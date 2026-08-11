# Inkling probe findings

<!-- inkling-probe:effort-field:start -->
## Effort-field controlled experiment

- Generated: `2026-07-16T01:08:41+00:00`
- Endpoint: `https://inference.baseten.co/v1`
- Model: `thinkingmachines/inkling`
- Samples requested: exactly `5` per (shape, level) and `5` no-effort controls (`110` total)
- Completed request records: `110`
- Fixed controls: `temperature=1`, `max_tokens=16384`, `stream=True`, `stream_options.include_usage=True`, identical messages/tools/tool_choice
- SDK retries: `0`; execution order is round-robin and strictly sequential (concurrency 1)

### Median reasoning tokens

| Request shape | Control | none | minimal | low | medium | high | xhigh | max | Classification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| nested extra_body.reasoning.effort | 84 | 0 | 80 | 70 | 78 | 123 | 84 | 77 | controls |
| top-level native reasoning_effort | 84 | 0 | 75 | 86 | 86 | 91 | 83 | 79 | controls |
| extra_body.chat_template_kwargs.reasoning_effort | 84 | 0 | 72 | 75 | 85 | 111 | 81 | 78 | controls |

### Exact decision rule and verdict

A shape controls iff `median(max) - median(none) >= 50`, `median(none) <= 5`, and it has no request-breaking 400 at any level. A shape is inert iff every level median is within 10 tokens of the no-effort control median. No adjacent-level monotonicity test is used.

Preference order is: top-level native `reasoning_effort`, then `chat_template_kwargs.reasoning_effort`, then nested `reasoning.effort`.

- Controlling shapes: `nested_reasoning_effort, native_reasoning_effort, chat_template_reasoning_effort`
- Inert shapes: `none`
- Selected controlling field: `top-level native reasoning_effort`
- Step 2 verdict: `PROCEED`
- Multiple controlling shapes were observed; this is normal and the preference order resolves selection.

### Per-request outcomes

| Sample | Shape | Level | HTTP | Error | 400 | Finish | Content chars | reasoning_content | Reasoning tokens | Seconds |
| ---: | --- | --- | ---: | --- | --- | --- | ---: | --- | ---: | ---: |
| 1 | control | — | 200 |  | no | tool_calls | 0 | yes | 86 | 1.476 |
| 1 | nested_reasoning_effort | none | 200 |  | no | tool_calls | 0 | no | 0 | 0.440 |
| 1 | nested_reasoning_effort | minimal | 200 |  | no | tool_calls | 0 | yes | 83 | 1.046 |
| 1 | nested_reasoning_effort | low | 200 |  | no | tool_calls | 0 | yes | 77 | 0.996 |
| 1 | nested_reasoning_effort | medium | 200 |  | no | tool_calls | 0 | yes | 84 | 1.038 |
| 1 | nested_reasoning_effort | high | 200 |  | no | tool_calls | 0 | yes | 133 | 1.329 |
| 1 | nested_reasoning_effort | xhigh | 200 |  | no | tool_calls | 0 | yes | 81 | 1.021 |
| 1 | nested_reasoning_effort | max | 200 |  | no | tool_calls | 0 | yes | 78 | 0.936 |
| 1 | native_reasoning_effort | none | 200 |  | no | tool_calls | 0 | no | 0 | 0.371 |
| 1 | native_reasoning_effort | minimal | 200 |  | no | tool_calls | 0 | yes | 82 | 0.970 |
| 1 | native_reasoning_effort | low | 200 |  | no | tool_calls | 0 | yes | 94 | 1.060 |
| 1 | native_reasoning_effort | medium | 200 |  | no | tool_calls | 0 | yes | 86 | 0.998 |
| 1 | native_reasoning_effort | high | 200 |  | no | tool_calls | 0 | yes | 137 | 1.355 |
| 1 | native_reasoning_effort | xhigh | 200 |  | no | tool_calls | 0 | yes | 86 | 1.004 |
| 1 | native_reasoning_effort | max | 200 |  | no | tool_calls | 0 | yes | 91 | 1.033 |
| 1 | chat_template_reasoning_effort | none | 200 |  | no | tool_calls | 0 | no | 0 | 0.372 |
| 1 | chat_template_reasoning_effort | minimal | 200 |  | no | tool_calls | 0 | yes | 65 | 0.854 |
| 1 | chat_template_reasoning_effort | low | 200 |  | no | tool_calls | 0 | yes | 77 | 0.942 |
| 1 | chat_template_reasoning_effort | medium | 200 |  | no | tool_calls | 0 | yes | 77 | 0.940 |
| 1 | chat_template_reasoning_effort | high | 200 |  | no | tool_calls | 0 | yes | 115 | 1.196 |
| 1 | chat_template_reasoning_effort | xhigh | 200 |  | no | tool_calls | 0 | yes | 77 | 0.944 |
| 1 | chat_template_reasoning_effort | max | 200 |  | no | tool_calls | 0 | yes | 78 | 0.946 |
| 2 | control | — | 200 |  | no | tool_calls | 0 | yes | 80 | 0.956 |
| 2 | nested_reasoning_effort | none | 200 |  | no | tool_calls | 0 | no | 0 | 0.375 |
| 2 | nested_reasoning_effort | minimal | 200 |  | no | tool_calls | 0 | yes | 80 | 0.957 |
| 2 | nested_reasoning_effort | low | 200 |  | no | tool_calls | 0 | yes | 88 | 1.003 |
| 2 | nested_reasoning_effort | medium | 200 |  | no | tool_calls | 0 | yes | 78 | 0.943 |
| 2 | nested_reasoning_effort | high | 200 |  | no | tool_calls | 0 | yes | 123 | 1.254 |
| 2 | nested_reasoning_effort | xhigh | 200 |  | no | tool_calls | 0 | yes | 90 | 1.031 |
| 2 | nested_reasoning_effort | max | 200 |  | no | tool_calls | 0 | yes | 77 | 0.938 |
| 2 | native_reasoning_effort | none | 200 |  | no | tool_calls | 0 | no | 0 | 0.378 |
| 2 | native_reasoning_effort | minimal | 200 |  | no | tool_calls | 0 | yes | 75 | 0.923 |
| 2 | native_reasoning_effort | low | 200 |  | no | tool_calls | 0 | yes | 75 | 0.923 |
| 2 | native_reasoning_effort | medium | 200 |  | no | tool_calls | 0 | yes | 77 | 0.934 |
| 2 | native_reasoning_effort | high | 200 |  | no | tool_calls | 0 | yes | 91 | 1.041 |
| 2 | native_reasoning_effort | xhigh | 200 |  | no | tool_calls | 0 | yes | 83 | 0.984 |
| 2 | native_reasoning_effort | max | 200 |  | no | tool_calls | 0 | yes | 78 | 0.945 |
| 2 | chat_template_reasoning_effort | none | 200 |  | no | tool_calls | 0 | no | 0 | 0.379 |
| 2 | chat_template_reasoning_effort | minimal | 200 |  | no | tool_calls | 0 | yes | 63 | 0.834 |
| 2 | chat_template_reasoning_effort | low | 200 |  | no | tool_calls | 0 | yes | 69 | 0.871 |
| 2 | chat_template_reasoning_effort | medium | 200 |  | no | tool_calls | 0 | yes | 85 | 0.994 |
| 2 | chat_template_reasoning_effort | high | 200 |  | no | tool_calls | 0 | yes | 98 | 1.139 |
| 2 | chat_template_reasoning_effort | xhigh | 200 |  | no | tool_calls | 0 | yes | 76 | 0.932 |
| 2 | chat_template_reasoning_effort | max | 200 |  | no | tool_calls | 0 | yes | 98 | 1.080 |
| 3 | control | — | 200 |  | no | tool_calls | 0 | yes | 105 | 1.138 |
| 3 | nested_reasoning_effort | none | 200 |  | no | tool_calls | 0 | no | 0 | 0.379 |
| 3 | nested_reasoning_effort | minimal | 200 |  | no | tool_calls | 0 | yes | 74 | 0.921 |
| 3 | nested_reasoning_effort | low | 200 |  | no | tool_calls | 0 | yes | 66 | 0.862 |
| 3 | nested_reasoning_effort | medium | 200 |  | no | tool_calls | 0 | yes | 78 | 0.939 |
| 3 | nested_reasoning_effort | high | 200 |  | no | tool_calls | 0 | yes | 95 | 1.071 |
| 3 | nested_reasoning_effort | xhigh | 200 |  | no | tool_calls | 0 | yes | 83 | 0.982 |
| 3 | nested_reasoning_effort | max | 200 |  | no | tool_calls | 0 | yes | 88 | 1.002 |
| 3 | native_reasoning_effort | none | 200 |  | no | tool_calls | 0 | no | 0 | 0.375 |
| 3 | native_reasoning_effort | minimal | 200 |  | no | tool_calls | 0 | yes | 87 | 1.011 |
| 3 | native_reasoning_effort | low | 200 |  | no | tool_calls | 0 | yes | 86 | 1.001 |
| 3 | native_reasoning_effort | medium | 200 |  | no | tool_calls | 0 | yes | 78 | 0.943 |
| 3 | native_reasoning_effort | high | 200 |  | no | tool_calls | 0 | yes | 86 | 0.993 |
| 3 | native_reasoning_effort | xhigh | 200 |  | no | tool_calls | 0 | yes | 96 | 1.073 |
| 3 | native_reasoning_effort | max | 200 |  | no | tool_calls | 0 | yes | 90 | 1.023 |
| 3 | chat_template_reasoning_effort | none | 200 |  | no | tool_calls | 0 | no | 0 | 0.388 |
| 3 | chat_template_reasoning_effort | minimal | 200 |  | no | tool_calls | 0 | yes | 81 | 0.967 |
| 3 | chat_template_reasoning_effort | low | 200 |  | no | tool_calls | 0 | yes | 74 | 0.909 |
| 3 | chat_template_reasoning_effort | medium | 200 |  | no | tool_calls | 0 | yes | 90 | 1.024 |
| 3 | chat_template_reasoning_effort | high | 200 |  | no | tool_calls | 0 | yes | 112 | 1.188 |
| 3 | chat_template_reasoning_effort | xhigh | 200 |  | no | tool_calls | 0 | yes | 120 | 1.239 |
| 3 | chat_template_reasoning_effort | max | 200 |  | no | tool_calls | 0 | yes | 80 | 0.955 |
| 4 | control | — | 200 |  | no | tool_calls | 0 | yes | 78 | 0.946 |
| 4 | nested_reasoning_effort | none | 200 |  | no | tool_calls | 0 | no | 0 | 0.378 |
| 4 | nested_reasoning_effort | minimal | 200 |  | no | tool_calls | 0 | yes | 69 | 0.876 |
| 4 | nested_reasoning_effort | low | 200 |  | no | tool_calls | 0 | yes | 70 | 0.887 |
| 4 | nested_reasoning_effort | medium | 200 |  | no | tool_calls | 0 | yes | 85 | 0.984 |
| 4 | nested_reasoning_effort | high | 200 |  | no | tool_calls | 0 | yes | 111 | 1.174 |
| 4 | nested_reasoning_effort | xhigh | 200 |  | no | tool_calls | 0 | yes | 84 | 0.987 |
| 4 | nested_reasoning_effort | max | 200 |  | no | tool_calls | 0 | yes | 77 | 0.940 |
| 4 | native_reasoning_effort | none | 200 |  | no | tool_calls | 0 | no | 0 | 0.375 |
| 4 | native_reasoning_effort | minimal | 200 |  | no | tool_calls | 0 | yes | 65 | 0.854 |
| 4 | native_reasoning_effort | low | 200 |  | no | tool_calls | 0 | yes | 86 | 0.992 |
| 4 | native_reasoning_effort | medium | 200 |  | no | tool_calls | 0 | yes | 86 | 1.005 |
| 4 | native_reasoning_effort | high | 200 |  | no | tool_calls | 0 | yes | 87 | 1.004 |
| 4 | native_reasoning_effort | xhigh | 200 |  | no | tool_calls | 0 | yes | 78 | 0.946 |
| 4 | native_reasoning_effort | max | 200 |  | no | tool_calls | 0 | yes | 79 | 0.951 |
| 4 | chat_template_reasoning_effort | none | 200 |  | no | tool_calls | 0 | no | 0 | 0.377 |
| 4 | chat_template_reasoning_effort | minimal | 200 |  | no | tool_calls | 0 | yes | 73 | 0.912 |
| 4 | chat_template_reasoning_effort | low | 200 |  | no | tool_calls | 0 | yes | 81 | 0.966 |
| 4 | chat_template_reasoning_effort | medium | 200 |  | no | tool_calls | 0 | yes | 79 | 0.950 |
| 4 | chat_template_reasoning_effort | high | 200 |  | no | tool_calls | 0 | yes | 83 | 0.978 |
| 4 | chat_template_reasoning_effort | xhigh | 200 |  | no | tool_calls | 0 | yes | 112 | 1.178 |
| 4 | chat_template_reasoning_effort | max | 200 |  | no | tool_calls | 0 | yes | 78 | 0.953 |
| 5 | control | — | 200 |  | no | tool_calls | 0 | yes | 84 | 0.990 |
| 5 | nested_reasoning_effort | none | 200 |  | no | tool_calls | 0 | no | 0 | 0.377 |
| 5 | nested_reasoning_effort | minimal | 200 |  | no | tool_calls | 0 | yes | 86 | 1.001 |
| 5 | nested_reasoning_effort | low | 200 |  | no | tool_calls | 0 | yes | 67 | 0.856 |
| 5 | nested_reasoning_effort | medium | 200 |  | no | tool_calls | 0 | yes | 76 | 0.922 |
| 5 | nested_reasoning_effort | high | 200 |  | no | tool_calls | 0 | yes | 156 | 1.498 |
| 5 | nested_reasoning_effort | xhigh | 200 |  | no | tool_calls | 0 | yes | 91 | 1.034 |
| 5 | nested_reasoning_effort | max | 200 |  | no | tool_calls | 0 | yes | 76 | 0.936 |
| 5 | native_reasoning_effort | none | 200 |  | no | tool_calls | 0 | no | 0 | 0.379 |
| 5 | native_reasoning_effort | minimal | 200 |  | no | tool_calls | 0 | yes | 51 | 0.750 |
| 5 | native_reasoning_effort | low | 200 |  | no | tool_calls | 0 | yes | 85 | 0.995 |
| 5 | native_reasoning_effort | medium | 200 |  | no | tool_calls | 0 | yes | 86 | 0.995 |
| 5 | native_reasoning_effort | high | 200 |  | no | tool_calls | 0 | yes | 108 | 1.220 |
| 5 | native_reasoning_effort | xhigh | 200 |  | no | tool_calls | 0 | yes | 78 | 0.940 |
| 5 | native_reasoning_effort | max | 200 |  | no | tool_calls | 0 | yes | 78 | 0.948 |
| 5 | chat_template_reasoning_effort | none | 200 |  | no | tool_calls | 0 | no | 0 | 0.380 |
| 5 | chat_template_reasoning_effort | minimal | 200 |  | no | tool_calls | 0 | yes | 72 | 0.962 |
| 5 | chat_template_reasoning_effort | low | 200 |  | no | tool_calls | 0 | yes | 75 | 0.968 |
| 5 | chat_template_reasoning_effort | medium | 200 |  | no | tool_calls | 0 | yes | 94 | 1.065 |
| 5 | chat_template_reasoning_effort | high | 200 |  | no | tool_calls | 0 | yes | 111 | 1.239 |
| 5 | chat_template_reasoning_effort | xhigh | 200 |  | no | tool_calls | 0 | yes | 81 | 0.970 |
| 5 | chat_template_reasoning_effort | max | 200 |  | no | tool_calls | 0 | yes | 78 | 0.979 |

### Raw sample records

The `request_kwargs_sent` object in every record is the exact Python keyword mapping passed to `chat.completions.create`; it is retained to prove that controls were mutually exclusive.

```json
[
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.4756857631728053,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.475276105105877,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.4752798730041832,
    "http_status": 200,
    "label": "control",
    "level": null,
    "reasoning_content_length": 220,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 86,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 1,
    "shape": "control",
    "started_utc": "2026-07-16T01:06:59+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-53d1341afaff46d6bcc247d837dbb41a",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 116
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.439782208064571,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": null,
    "first_reasoning_secs": null,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.4395033079199493,
    "http_status": 200,
    "label": "nested_reasoning_effort:none",
    "level": "none",
    "reasoning_content_length": 0,
    "reasoning_content_present": false,
    "reasoning_delta_count": 0,
    "reasoning_same_delta_as_first_answer": null,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 0,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "none"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 1,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:07:00+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-1c819c6dcad1412a954c1ea9d581c783",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 27
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.0461265039630234,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.0458125879522413,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.0458161439746618,
    "http_status": 200,
    "label": "nested_reasoning_effort:minimal",
    "level": "minimal",
    "reasoning_content_length": 206,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 83,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "minimal"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 1,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:07:01+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-c342b0d0651841d1bf9977b39f2577e2",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 113
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.995592116843909,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9953070560004562,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.995308178011328,
    "http_status": 200,
    "label": "nested_reasoning_effort:low",
    "level": "low",
    "reasoning_content_length": 181,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 77,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "low"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 1,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:07:02+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-0fe1cfaf8ec14fbdbd0931222e735cb3",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 107
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.0375678359996527,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.0373533489182591,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.0373547519557178,
    "http_status": 200,
    "label": "nested_reasoning_effort:medium",
    "level": "medium",
    "reasoning_content_length": 210,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 84,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "medium"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 1,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:07:03+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-fc77599a28be43efad47f5a64333540c",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 114
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.3291904269717634,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.3289755887817591,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.3289769208058715,
    "http_status": 200,
    "label": "nested_reasoning_effort:high",
    "level": "high",
    "reasoning_content_length": 371,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 133,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "high"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 1,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:07:04+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-810f5121ed1442d7a380da09c2215395",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 163
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.0213002969976515,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.0210842362139374,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.021085489075631,
    "http_status": 200,
    "label": "nested_reasoning_effort:xhigh",
    "level": "xhigh",
    "reasoning_content_length": 194,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 81,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "xhigh"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 1,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:07:05+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-ef9ed553612444e7b3ae167416a8fbd1",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 111
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9360801491420716,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9358675749972463,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9358687880448997,
    "http_status": 200,
    "label": "nested_reasoning_effort:max",
    "level": "max",
    "reasoning_content_length": 188,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 78,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "max"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 1,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:07:06+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-9782c5d6e87544f9ab60613c4d5878c2",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 108
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.37107707606628537,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": null,
    "first_reasoning_secs": null,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.37082305387593806,
    "http_status": 200,
    "label": "native_reasoning_effort:none",
    "level": "none",
    "reasoning_content_length": 0,
    "reasoning_content_present": false,
    "reasoning_delta_count": 0,
    "reasoning_same_delta_as_first_answer": null,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 0,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "none",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 1,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:07:07+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-d343c0018e7c41b9a9b9ebff3624a21b",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 27
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9698356140870601,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9696114780381322,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9696134021505713,
    "http_status": 200,
    "label": "native_reasoning_effort:minimal",
    "level": "minimal",
    "reasoning_content_length": 190,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 82,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "minimal",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 1,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:07:08+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-a47a8e28220c4e529f09f55d12ccac7c",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 112
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.0598798550199717,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.0595642558764666,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.0595661788247526,
    "http_status": 200,
    "label": "native_reasoning_effort:low",
    "level": "low",
    "reasoning_content_length": 284,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 94,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "low",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 1,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:07:09+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-801eea798f9143869be77a12237f9884",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 124
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.997614525957033,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9973996579647064,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9974009511061013,
    "http_status": 200,
    "label": "native_reasoning_effort:medium",
    "level": "medium",
    "reasoning_content_length": 214,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 86,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "medium",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 1,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:07:10+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-927cfde4739d4654881d1266ee14f98c",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 116
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.3548698399681598,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.3546046558767557,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.3546059189829975,
    "http_status": 200,
    "label": "native_reasoning_effort:high",
    "level": "high",
    "reasoning_content_length": 351,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 137,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "high",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 1,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:07:11+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-42abccffc1964f019ac9adb97b6ba3b9",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 167
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.0044528949074447,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.0042256729211658,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.0042271460406482,
    "http_status": 200,
    "label": "native_reasoning_effort:xhigh",
    "level": "xhigh",
    "reasoning_content_length": 208,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 86,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "xhigh",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 1,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:07:12+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-670541e0e29549ceaaa8fca03efc464f",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 116
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.0331059989985079,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.032862045103684,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.0328638390637934,
    "http_status": 200,
    "label": "native_reasoning_effort:max",
    "level": "max",
    "reasoning_content_length": 243,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 91,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "max",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 1,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:07:13+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-d466976e87fe4182aa521c37ac23f5f3",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 121
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.37156445207074285,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": null,
    "first_reasoning_secs": null,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.3713096280116588,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:none",
    "level": "none",
    "reasoning_content_length": 0,
    "reasoning_content_present": false,
    "reasoning_delta_count": 0,
    "reasoning_same_delta_as_first_answer": null,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 0,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "none"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 1,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:07:14+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-1fe757c9076c4f84a6b749b98719e300",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 27
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.8539796539116651,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.8537000028882176,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.8537018168717623,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:minimal",
    "level": "minimal",
    "reasoning_content_length": 135,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 65,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "minimal"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 1,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:07:14+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-e3c84a81d12f4a6587e4aa338b7126fc",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 95
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9419281838927418,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9412544039078057,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9412555960007012,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:low",
    "level": "low",
    "reasoning_content_length": 182,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 77,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "low"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 1,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:07:15+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-a82a4c15857d4d26be531811a97b416f",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 107
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9396460289135575,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9393661168869585,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9393677399493754,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:medium",
    "level": "medium",
    "reasoning_content_length": 180,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 77,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "medium"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 1,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:07:16+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-b4d66e844c03486baa9cc2cc17eb3e07",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 107
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.1957111000083387,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.195479268906638,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.1954809930175543,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:high",
    "level": "high",
    "reasoning_content_length": 268,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 115,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "high"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 1,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:07:17+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-4facbb1263564ebcb6c9c504cc0f5cd3",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 145
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9440451839473099,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9438299050088972,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9438313378486782,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:xhigh",
    "level": "xhigh",
    "reasoning_content_length": 188,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 77,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "xhigh"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 1,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:07:18+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-90f48afd964c4358a2aeec9dff6069e3",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 107
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9455308658070862,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.945271453820169,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9452726959716529,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:max",
    "level": "max",
    "reasoning_content_length": 190,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 78,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "max"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 1,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:07:19+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-711cb0dfb9b34aa989e80fd111b7115e",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 108
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9555380730889738,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9552970449440181,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9552987380884588,
    "http_status": 200,
    "label": "control",
    "level": null,
    "reasoning_content_length": 202,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 80,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 2,
    "shape": "control",
    "started_utc": "2026-07-16T01:07:20+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-ee585dfbb1f548bd9eacd02376ddba0c",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 110
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.3754875829908997,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": null,
    "first_reasoning_secs": null,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.37520354404114187,
    "http_status": 200,
    "label": "nested_reasoning_effort:none",
    "level": "none",
    "reasoning_content_length": 0,
    "reasoning_content_present": false,
    "reasoning_delta_count": 0,
    "reasoning_same_delta_as_first_answer": null,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 0,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "none"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 2,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:07:21+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-1753d8ae987443288898eb59d5ba0b5c",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 27
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9569338238798082,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9566968439612538,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9566985270939767,
    "http_status": 200,
    "label": "nested_reasoning_effort:minimal",
    "level": "minimal",
    "reasoning_content_length": 174,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 80,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "minimal"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 2,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:07:22+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-95900fd1ac154703b1c63c4c77d8bc84",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 110
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.0031214328482747,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.002890383824706,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.0028916858136654,
    "http_status": 200,
    "label": "nested_reasoning_effort:low",
    "level": "low",
    "reasoning_content_length": 202,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 88,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "low"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 2,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:07:23+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-2261a457caa64bd4a55925356e160ff1",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 118
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9432281600311399,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9429998169653118,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9430012491066009,
    "http_status": 200,
    "label": "nested_reasoning_effort:medium",
    "level": "medium",
    "reasoning_content_length": 189,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 78,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "medium"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 2,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:07:24+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-520173fc4e42491c8e472c5124fd3527",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 108
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.2535892608575523,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.25334909488447,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.2533507379703224,
    "http_status": 200,
    "label": "nested_reasoning_effort:high",
    "level": "high",
    "reasoning_content_length": 265,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 123,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "high"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 2,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:07:25+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-18e742435f6f4396806e808f7f6ab71d",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 153
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.0312402511481196,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.0309882319997996,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.0309894641395658,
    "http_status": 200,
    "label": "nested_reasoning_effort:xhigh",
    "level": "xhigh",
    "reasoning_content_length": 211,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 90,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "xhigh"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 2,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:07:26+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-143819f3776648fa95d5a5542b6f1763",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 120
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9377515478990972,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9374549649655819,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9374562469311059,
    "http_status": 200,
    "label": "nested_reasoning_effort:max",
    "level": "max",
    "reasoning_content_length": 192,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 77,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "max"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 2,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:07:27+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-e06ebce07be1490bb7c1f0fa167973fa",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 107
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.37770113605074584,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": null,
    "first_reasoning_secs": null,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.37738938396796584,
    "http_status": 200,
    "label": "native_reasoning_effort:none",
    "level": "none",
    "reasoning_content_length": 0,
    "reasoning_content_present": false,
    "reasoning_delta_count": 0,
    "reasoning_same_delta_as_first_answer": null,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 0,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "none",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 2,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:07:28+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-813b364b3eb246ec9c8deae5baad3d0e",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 27
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9229218100663275,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.922687916085124,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9226895391475409,
    "http_status": 200,
    "label": "native_reasoning_effort:minimal",
    "level": "minimal",
    "reasoning_content_length": 174,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 75,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "minimal",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 2,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:07:28+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-00c263568c924a7ab479e2eb252d5a7b",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 105
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.923237849958241,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9229552028700709,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9229569158051163,
    "http_status": 200,
    "label": "native_reasoning_effort:low",
    "level": "low",
    "reasoning_content_length": 174,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 75,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "low",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 2,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:07:29+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-144b67d678a04551bb7fe88478fc50f4",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 105
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9335438250564039,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9332571600098163,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9332586631644517,
    "http_status": 200,
    "label": "native_reasoning_effort:medium",
    "level": "medium",
    "reasoning_content_length": 180,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 77,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "medium",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 2,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:07:30+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-609081e46ba14764a151151a14fee5c2",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 107
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.040983385173604,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.0407379490789026,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.0407428580801934,
    "http_status": 200,
    "label": "native_reasoning_effort:high",
    "level": "high",
    "reasoning_content_length": 244,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 91,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "high",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 2,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:07:31+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-ed711693a35f40bea54ca642815af4b2",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 121
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9844684801064432,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9842225830070674,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9842240260913968,
    "http_status": 200,
    "label": "native_reasoning_effort:xhigh",
    "level": "xhigh",
    "reasoning_content_length": 205,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 83,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "xhigh",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 2,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:07:32+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-933f3dba1aea45ac8d606b7277d16dcf",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 113
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9445662300568074,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.944317267043516,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.944318959955126,
    "http_status": 200,
    "label": "native_reasoning_effort:max",
    "level": "max",
    "reasoning_content_length": 194,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 78,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "max",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 2,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:07:33+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-74cd9461cd614a8f9d4423c89e596ce7",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 108
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.3785778109449893,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": null,
    "first_reasoning_secs": null,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.37827845197170973,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:none",
    "level": "none",
    "reasoning_content_length": 0,
    "reasoning_content_present": false,
    "reasoning_delta_count": 0,
    "reasoning_same_delta_as_first_answer": null,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 0,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "none"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 2,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:07:34+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-dba5ba8722d648a484924a0aa64d9e11",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 27
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.8335147590842098,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.8332055611535907,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.833207585150376,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:minimal",
    "level": "minimal",
    "reasoning_content_length": 130,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 63,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "minimal"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 2,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:07:34+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-7e784e4c0c4e44bd96c228c30b02f8fb",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 93
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.8706830251030624,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.870478737168014,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.8704797991085798,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:low",
    "level": "low",
    "reasoning_content_length": 150,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 69,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "low"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 2,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:07:35+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-f0c2a9b7881f4b01941646a2403463e7",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 99
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9936186489649117,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9933965569362044,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9933977990876883,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:medium",
    "level": "medium",
    "reasoning_content_length": 202,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 85,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "medium"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 2,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:07:36+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-212b905667f34104b2de2d9339cf4ce2",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 115
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.1394216970074922,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.1391931630205363,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.1391943849157542,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:high",
    "level": "high",
    "reasoning_content_length": 255,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 98,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "high"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 2,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:07:37+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-7c9df9761ff34ad6910f89b0e02a514f",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 128
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9322361091617495,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9320270221214741,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9320281040854752,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:xhigh",
    "level": "xhigh",
    "reasoning_content_length": 176,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 76,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "xhigh"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 2,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:07:38+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-3caa7b6f00944467aeba0a531dea9869",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 106
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.0800856840796769,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.0798010730650276,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.0798026560805738,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:max",
    "level": "max",
    "reasoning_content_length": 259,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 98,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "max"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 2,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:07:39+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-2e732579636044caad47eab3fc3acb5f",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 128
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.1376096941530704,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.1374008171260357,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.1374018790666014,
    "http_status": 200,
    "label": "control",
    "level": null,
    "reasoning_content_length": 260,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 105,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 3,
    "shape": "control",
    "started_utc": "2026-07-16T01:07:40+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-faf3507d2413481f9f023ed0ab530b8e",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 135
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.37938114581629634,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": null,
    "first_reasoning_secs": null,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.37912241485901177,
    "http_status": 200,
    "label": "nested_reasoning_effort:none",
    "level": "none",
    "reasoning_content_length": 0,
    "reasoning_content_present": false,
    "reasoning_delta_count": 0,
    "reasoning_same_delta_as_first_answer": null,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 0,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "none"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 3,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:07:41+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-6f9cd278b8774da2898e4111fb1b56c5",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 27
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9214070590678602,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9211833840236068,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9211845260579139,
    "http_status": 200,
    "label": "nested_reasoning_effort:minimal",
    "level": "minimal",
    "reasoning_content_length": 177,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 74,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "minimal"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 3,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:07:42+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-0b1ed5f16ef3488a988126b195714f30",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 104
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.8618353381752968,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.861554304137826,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.8615555861033499,
    "http_status": 200,
    "label": "nested_reasoning_effort:low",
    "level": "low",
    "reasoning_content_length": 132,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 66,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "low"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 3,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:07:43+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-98ca0917ff1f426aaf341fcaedf2c104",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 96
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9387542868498713,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9385318749118596,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9385330369696021,
    "http_status": 200,
    "label": "nested_reasoning_effort:medium",
    "level": "medium",
    "reasoning_content_length": 197,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 78,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "medium"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 3,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:07:43+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-456a11ae40e54918bae287479ac730d6",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 108
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.07081394107081,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.070485366974026,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.070486729964614,
    "http_status": 200,
    "label": "nested_reasoning_effort:high",
    "level": "high",
    "reasoning_content_length": 280,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 95,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "high"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 3,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:07:44+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-d9ce0cf9375c42cb9209a1488fe63858",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 125
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9819804797880352,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9816597409080714,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9816613839939237,
    "http_status": 200,
    "label": "nested_reasoning_effort:xhigh",
    "level": "xhigh",
    "reasoning_content_length": 200,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 83,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "xhigh"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 3,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:07:45+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-30c508124ec2431e9d2a4f95f97d02da",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 113
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.0017081410624087,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.0013925910461694,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.001393703976646,
    "http_status": 200,
    "label": "nested_reasoning_effort:max",
    "level": "max",
    "reasoning_content_length": 216,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 88,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "max"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 3,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:07:46+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-c5f13e12494447118b6d54198d65aeda",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 118
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.3746195000130683,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": null,
    "first_reasoning_secs": null,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.37434083106927574,
    "http_status": 200,
    "label": "native_reasoning_effort:none",
    "level": "none",
    "reasoning_content_length": 0,
    "reasoning_content_present": false,
    "reasoning_delta_count": 0,
    "reasoning_same_delta_as_first_answer": null,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 0,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "none",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 3,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:07:47+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-a2ed646cda8548139b0e18a6c649d4bc",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 27
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.0112674271222204,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.0110109101515263,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.0110126631334424,
    "http_status": 200,
    "label": "native_reasoning_effort:minimal",
    "level": "minimal",
    "reasoning_content_length": 252,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 87,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "minimal",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 3,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:07:48+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-4fb04f95c46a421ab1b6778de9d7748c",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 117
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.0005922198761255,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.0003714710474014,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.0003732440527529,
    "http_status": 200,
    "label": "native_reasoning_effort:low",
    "level": "low",
    "reasoning_content_length": 202,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 86,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "low",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 3,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:07:49+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-f79fda67c75f4f8da2b54f2aa519cdfc",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 116
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9431547040585428,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9428553560283035,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9428573600016534,
    "http_status": 200,
    "label": "native_reasoning_effort:medium",
    "level": "medium",
    "reasoning_content_length": 186,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 78,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "medium",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 3,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:07:50+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-4a06c0a87e4b40ce86ae15896ba22b4b",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 108
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9932751420419663,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9930629190057516,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9930643308907747,
    "http_status": 200,
    "label": "native_reasoning_effort:high",
    "level": "high",
    "reasoning_content_length": 225,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 86,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "high",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 3,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:07:51+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-42d400840f5041369e163fddb40c2a15",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 116
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.073274492053315,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.0730515390168875,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.0730527909472585,
    "http_status": 200,
    "label": "native_reasoning_effort:xhigh",
    "level": "xhigh",
    "reasoning_content_length": 239,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 96,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "xhigh",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 3,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:07:52+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-ee37cb0ddeea4558a59a262890123449",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 126
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.0231041188817471,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.02285944391042,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.0228610169142485,
    "http_status": 200,
    "label": "native_reasoning_effort:max",
    "level": "max",
    "reasoning_content_length": 211,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 90,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "max",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 3,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:07:53+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-8c79f5844a964a88ada2c7afbd4f6d31",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 120
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.3880091430619359,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": null,
    "first_reasoning_secs": null,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.3877124690916389,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:none",
    "level": "none",
    "reasoning_content_length": 0,
    "reasoning_content_present": false,
    "reasoning_delta_count": 0,
    "reasoning_same_delta_as_first_answer": null,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 0,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "none"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 3,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:07:54+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-0daae516a0af4e0d90afc801d05d43fb",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 27
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9667058747727424,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9664846549276263,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9664859678596258,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:minimal",
    "level": "minimal",
    "reasoning_content_length": 194,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 81,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "minimal"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 3,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:07:54+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-f0da2087c81743dfa0c983ee8b2f8416",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 111
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9088124129921198,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9085308779031038,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9085322108585387,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:low",
    "level": "low",
    "reasoning_content_length": 176,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 74,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "low"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 3,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:07:55+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-c3d493ee67b6491d9d9814137faa18c7",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 104
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.0240330919623375,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.0237990070600063,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.0238006201107055,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:medium",
    "level": "medium",
    "reasoning_content_length": 212,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 90,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "medium"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 3,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:07:56+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-61321d19165940619e6f06f32bb67e54",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 120
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.187966956058517,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.1876664459705353,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.1876677181571722,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:high",
    "level": "high",
    "reasoning_content_length": 289,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 112,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "high"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 3,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:07:57+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-61f8ff3313ff4a61af71c5acac89e915",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 142
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.2392219689209014,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.2389278910122812,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.2389291829895228,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:xhigh",
    "level": "xhigh",
    "reasoning_content_length": 279,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 120,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "xhigh"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 3,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:07:58+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-4816a08aa9054245ae9b163db7fa3eb9",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 150
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9552100198343396,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.954919156851247,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.954920579912141,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:max",
    "level": "max",
    "reasoning_content_length": 188,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 80,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "max"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 3,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:08:00+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-62dd2396fe414e28bcd20790e5546afb",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 110
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9455159059725702,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9452981119975448,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9452995350584388,
    "http_status": 200,
    "label": "control",
    "level": null,
    "reasoning_content_length": 186,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 78,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 4,
    "shape": "control",
    "started_utc": "2026-07-16T01:08:00+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-eb65c1ad3e7c41fda53c5bff9560336e",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 108
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.3783165419008583,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": null,
    "first_reasoning_secs": null,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.3780093479435891,
    "http_status": 200,
    "label": "nested_reasoning_effort:none",
    "level": "none",
    "reasoning_content_length": 0,
    "reasoning_content_present": false,
    "reasoning_delta_count": 0,
    "reasoning_same_delta_as_first_answer": null,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 0,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "none"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 4,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:08:01+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-37f09387ecd0425faf5793aad5d800b0",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 27
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.8764862010721117,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.8762410960625857,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.8762428991030902,
    "http_status": 200,
    "label": "nested_reasoning_effort:minimal",
    "level": "minimal",
    "reasoning_content_length": 150,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 69,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "minimal"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 4,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:08:02+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-ed93a43a879b464c82eba662833968e6",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 99
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.8871974558569491,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.8869327330030501,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.8869337849318981,
    "http_status": 200,
    "label": "nested_reasoning_effort:low",
    "level": "low",
    "reasoning_content_length": 158,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 70,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "low"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 4,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:08:03+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-0fc42075a64a4f528bbdca954ef7277d",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 100
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9838247380685061,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9835374020040035,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9835388250648975,
    "http_status": 200,
    "label": "nested_reasoning_effort:medium",
    "level": "medium",
    "reasoning_content_length": 200,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 85,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "medium"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 4,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:08:04+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-6027862500c6472baee11b11a40b93e4",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 115
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.173811708111316,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.1735591581091285,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.1735607509035617,
    "http_status": 200,
    "label": "nested_reasoning_effort:high",
    "level": "high",
    "reasoning_content_length": 325,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 111,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "high"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 4,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:08:05+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-0faa7f39a674432cb32cb86bea73ba9b",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 141
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.987414597067982,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9870481209363788,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9870511260814965,
    "http_status": 200,
    "label": "nested_reasoning_effort:xhigh",
    "level": "xhigh",
    "reasoning_content_length": 200,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 84,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "xhigh"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 4,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:08:06+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-074c874d204148078615be5c3193a2ad",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 114
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9403580569196492,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9400676058139652,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9400695490185171,
    "http_status": 200,
    "label": "nested_reasoning_effort:max",
    "level": "max",
    "reasoning_content_length": 180,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 77,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "max"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 4,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:08:07+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-229a3a20580a4d53bee058ce2590b8c2",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 107
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.37530661397613585,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": null,
    "first_reasoning_secs": null,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.37493642093613744,
    "http_status": 200,
    "label": "native_reasoning_effort:none",
    "level": "none",
    "reasoning_content_length": 0,
    "reasoning_content_present": false,
    "reasoning_delta_count": 0,
    "reasoning_same_delta_as_first_answer": null,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 0,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "none",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 4,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:08:08+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-3c0e7aef41654ba29b31d69897037003",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 27
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.8541390229947865,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.8537626480683684,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.853765033185482,
    "http_status": 200,
    "label": "native_reasoning_effort:minimal",
    "level": "minimal",
    "reasoning_content_length": 133,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 65,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "minimal",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 4,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:08:08+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-ad05fb4e96cb490bbfcd10d793e964a0",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 95
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.99171181791462,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9914767218288034,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9914783048443496,
    "http_status": 200,
    "label": "native_reasoning_effort:low",
    "level": "low",
    "reasoning_content_length": 198,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 86,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "low",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 4,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:08:09+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-5d4ca657eb7a4004b7801aca2037f1e4",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 116
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.005112721119076,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.0048181610181928,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.0048200450837612,
    "http_status": 200,
    "label": "native_reasoning_effort:medium",
    "level": "medium",
    "reasoning_content_length": 206,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 86,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "medium",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 4,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:08:10+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-c3997ed43774434ab0c538e48806a076",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 116
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.0039781860541552,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.0036269291304052,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.0036283009685576,
    "http_status": 200,
    "label": "native_reasoning_effort:high",
    "level": "high",
    "reasoning_content_length": 235,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 87,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "high",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 4,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:08:11+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-4b3c760c1c1845409ac2aa39a15dd03f",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 117
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9460283149965107,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9456614688970149,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.945663922931999,
    "http_status": 200,
    "label": "native_reasoning_effort:xhigh",
    "level": "xhigh",
    "reasoning_content_length": 186,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 78,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "xhigh",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 4,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:08:12+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-3608fc0cb1694382a8cd450d367534db",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 108
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9508778669405729,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.95049315597862,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9504947289824486,
    "http_status": 200,
    "label": "native_reasoning_effort:max",
    "level": "max",
    "reasoning_content_length": 189,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 79,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "max",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 4,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:08:13+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-bc3c5e45a2ef409d82ee3212c24e2afd",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 109
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.37690129317343235,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": null,
    "first_reasoning_secs": null,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.3766189960297197,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:none",
    "level": "none",
    "reasoning_content_length": 0,
    "reasoning_content_present": false,
    "reasoning_delta_count": 0,
    "reasoning_same_delta_as_first_answer": null,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 0,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "none"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 4,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:08:14+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-875bf2eb7b6b47d4bc23f33acf5890f2",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 27
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9119237379636616,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9115447481162846,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9115469621028751,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:minimal",
    "level": "minimal",
    "reasoning_content_length": 174,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 73,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "minimal"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 4,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:08:14+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-5f29deff7feb480f9247f6253b7256b4",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 103
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9659160990267992,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9656283131334931,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9656298060435802,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:low",
    "level": "low",
    "reasoning_content_length": 182,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 81,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "low"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 4,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:08:15+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-93bb3f3ab7dd44f699c1d252eab5c100",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 111
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9500224420335144,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.949417081894353,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9494210700504482,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:medium",
    "level": "medium",
    "reasoning_content_length": 194,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 79,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "medium"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 4,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:08:16+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-aa9201f702244aab9791cc8dad94314e",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 109
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9776633819565177,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9772639439906925,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9772654969710857,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:high",
    "level": "high",
    "reasoning_content_length": 198,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 83,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "high"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 4,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:08:17+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-7e2e2c3237b24ea39b9485250b029992",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 113
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.1781570971943438,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.1778992370236665,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.1779005501884967,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:xhigh",
    "level": "xhigh",
    "reasoning_content_length": 270,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 112,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "xhigh"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 4,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:08:18+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-1aaa261c23b1423d8cdcf4f67dff6aa7",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 142
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9528354438953102,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9525813211221248,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.952582583995536,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:max",
    "level": "max",
    "reasoning_content_length": 186,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 78,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "max"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 4,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:08:19+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-743c344faebb4e6188cf9ed95ac8b758",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 108
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9902834910899401,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9900017860345542,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9900037301704288,
    "http_status": 200,
    "label": "control",
    "level": null,
    "reasoning_content_length": 211,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 84,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 5,
    "shape": "control",
    "started_utc": "2026-07-16T01:08:20+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-51434486b1c944ae8fe8e84e13ca7ed7",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 114
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.3767435010522604,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": null,
    "first_reasoning_secs": null,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.3764818850904703,
    "http_status": 200,
    "label": "nested_reasoning_effort:none",
    "level": "none",
    "reasoning_content_length": 0,
    "reasoning_content_present": false,
    "reasoning_delta_count": 0,
    "reasoning_same_delta_as_first_answer": null,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 0,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "none"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 5,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:08:21+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-764fdd6593024eccbcefe641c8425455",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 27
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.0010329389479011,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.0008000459056348,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.0008012889884412,
    "http_status": 200,
    "label": "nested_reasoning_effort:minimal",
    "level": "minimal",
    "reasoning_content_length": 198,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 86,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "minimal"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 5,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:08:21+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-2cedbd7ef35a4e549f3f7c2ac03fd026",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 116
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.856406998122111,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.8560366041492671,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.8560381270945072,
    "http_status": 200,
    "label": "nested_reasoning_effort:low",
    "level": "low",
    "reasoning_content_length": 144,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 67,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "low"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 5,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:08:22+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-d6f99801b1d640c199c7518ecc0a895f",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 97
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9221271860878915,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9218353522010148,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9218370751477778,
    "http_status": 200,
    "label": "nested_reasoning_effort:medium",
    "level": "medium",
    "reasoning_content_length": 176,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 76,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "medium"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 5,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:08:23+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-18c00a154e2646a0ac8d1df3464081d8",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 106
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.4979180051013827,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.4975437140092254,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.49754534708336,
    "http_status": 200,
    "label": "nested_reasoning_effort:high",
    "level": "high",
    "reasoning_content_length": 381,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 156,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "high"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 5,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:08:24+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-a5532b6c19df4755987b2440e5876449",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 186
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.0336500501725823,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.0334048040676862,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.03340656706132,
    "http_status": 200,
    "label": "nested_reasoning_effort:xhigh",
    "level": "xhigh",
    "reasoning_content_length": 229,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 91,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "xhigh"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 5,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:08:26+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-17caaf80b86a4d50ad348b5f09ad708c",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 121
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.936280878027901,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9360081199556589,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9360096130985767,
    "http_status": 200,
    "label": "nested_reasoning_effort:max",
    "level": "max",
    "reasoning_content_length": 182,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 76,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "reasoning": {
          "effort": "max"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 5,
    "shape": "nested_reasoning_effort",
    "started_utc": "2026-07-16T01:08:27+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-5a7e12edc4154b2eb0763ddf3e8cd110",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 106
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.3794379490427673,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": null,
    "first_reasoning_secs": null,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.3791537790093571,
    "http_status": 200,
    "label": "native_reasoning_effort:none",
    "level": "none",
    "reasoning_content_length": 0,
    "reasoning_content_present": false,
    "reasoning_delta_count": 0,
    "reasoning_same_delta_as_first_answer": null,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 0,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "none",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 5,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:08:28+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-b0575bd29d6246d8b985c32ae6c61c93",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 27
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.7495839279145002,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.7491958010941744,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.7491975750308484,
    "http_status": 200,
    "label": "native_reasoning_effort:minimal",
    "level": "minimal",
    "reasoning_content_length": 138,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 51,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "minimal",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 5,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:08:28+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-b379635bdde94719b4392812608c648b",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 81
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9954765429720283,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9952215088997036,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.995223281905055,
    "http_status": 200,
    "label": "native_reasoning_effort:low",
    "level": "low",
    "reasoning_content_length": 194,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 85,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "low",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 5,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:08:29+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-73729f342c5d490ea1dee6e310a005a8",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 115
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9953768539708108,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9950493921060115,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9950511350762099,
    "http_status": 200,
    "label": "native_reasoning_effort:medium",
    "level": "medium",
    "reasoning_content_length": 208,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 86,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "medium",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 5,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:08:30+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-9ea876e6f28c4e0cbac66f419ad20569",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 116
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.2203051878605038,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.2200615748297423,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.2200632588937879,
    "http_status": 200,
    "label": "native_reasoning_effort:high",
    "level": "high",
    "reasoning_content_length": 260,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 108,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "high",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 5,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:08:31+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-f651dd4adf2f4ba380c914130e296aff",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 138
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9402049907948822,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9399762959219515,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9399780798703432,
    "http_status": 200,
    "label": "native_reasoning_effort:xhigh",
    "level": "xhigh",
    "reasoning_content_length": 182,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 78,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "xhigh",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 5,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:08:32+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-ccf4329fc210400db7c00004a9b49a5e",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 108
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9475118580739945,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9472023001872003,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.947204384021461,
    "http_status": 200,
    "label": "native_reasoning_effort:max",
    "level": "max",
    "reasoning_content_length": 192,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 78,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "reasoning_effort": "max",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 5,
    "shape": "native_reasoning_effort",
    "started_utc": "2026-07-16T01:08:33+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-d5f9f65a5d114e5bb13e8207b06610e6",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 108
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.37955684401094913,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": null,
    "first_reasoning_secs": null,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.37910748994909227,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:none",
    "level": "none",
    "reasoning_content_length": 0,
    "reasoning_content_present": false,
    "reasoning_delta_count": 0,
    "reasoning_same_delta_as_first_answer": null,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 0,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "none"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 5,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:08:34+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-555cb30f421c4c838cc0e86e08431ba1",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 27
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9618948369752616,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9614837761037052,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9614856399130076,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:minimal",
    "level": "minimal",
    "reasoning_content_length": 164,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 72,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "minimal"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 5,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:08:34+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-9e68087047604aa199c86e1841d6e20d",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 102
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9677665599156171,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.967529198853299,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9675304109696299,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:low",
    "level": "low",
    "reasoning_content_length": 180,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 75,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "low"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 5,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:08:35+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-728ba23dcd234f07b6c21d38b4a08f46",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 105
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.065067590912804,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.0648330159019679,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.0648346787784249,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:medium",
    "level": "medium",
    "reasoning_content_length": 236,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 94,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "medium"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 5,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:08:36+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-ab9ae1a3b88a40d39a89f27d11778afe",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 124
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 1.2385150839108974,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 1.2382134310901165,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 1.2382148439064622,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:high",
    "level": "high",
    "reasoning_content_length": 264,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 111,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "high"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 5,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:08:37+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-ed9f03166c974e1fb54dd2726a069a8f",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 141
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9701195780653507,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9698745929636061,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9698758749291301,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:xhigh",
    "level": "xhigh",
    "reasoning_content_length": 195,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 81,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "xhigh"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 5,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:08:39+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-7dc048f5e2c9423a99473ad8bcb2943a",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 111
  },
  {
    "content_length": 0,
    "content_preview": "",
    "elapsed_secs": 0.9786077290773392,
    "error_body": null,
    "error_message": null,
    "error_type": null,
    "finish_reason": "tool_calls",
    "first_answer_chunk_index": 0,
    "first_content_chunk_index": null,
    "first_content_secs": null,
    "first_reasoning_chunk_index": 0,
    "first_reasoning_secs": 0.9783698879182339,
    "first_tool_call_chunk_index": 0,
    "first_tool_call_secs": 0.9783709601033479,
    "http_status": 200,
    "label": "chat_template_reasoning_effort:max",
    "level": "max",
    "reasoning_content_length": 201,
    "reasoning_content_present": true,
    "reasoning_delta_count": 1,
    "reasoning_same_delta_as_first_answer": true,
    "reasoning_same_delta_as_first_content": null,
    "reasoning_tokens": 78,
    "request_breaking_400": false,
    "request_kwargs_sent": {
      "extra_body": {
        "chat_template_kwargs": {
          "reasoning_effort": "max"
        }
      },
      "max_tokens": 16384,
      "messages": [
        {
          "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
          "role": "system"
        },
        {
          "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
          "role": "user"
        }
      ],
      "model": "thinkingmachines/inkling",
      "stream": true,
      "stream_options": {
        "include_usage": true
      },
      "temperature": 1.0,
      "tool_choice": {
        "function": {
          "name": "submit_probe"
        },
        "type": "function"
      },
      "tools": [
        {
          "function": {
            "description": "Submit the answer for the controlled Inkling probe.",
            "name": "submit_probe",
            "parameters": {
              "additionalProperties": false,
              "properties": {
                "answer": {
                  "type": "integer"
                },
                "checksum": {
                  "type": "string"
                }
              },
              "required": [
                "answer",
                "checksum"
              ],
              "type": "object"
            }
          },
          "type": "function"
        }
      ]
    },
    "response_headers": {},
    "sample": 5,
    "shape": "chat_template_reasoning_effort",
    "started_utc": "2026-07-16T01:08:40+00:00",
    "tool_calls": [
      {
        "arguments_json_error": null,
        "arguments_json_valid": true,
        "arguments_length": 53,
        "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
        "id": "chatcmpl-tool-4bce7f9ddcdd4beca6319065701dcff0",
        "index": 0,
        "name": "submit_probe",
        "type": "function"
      }
    ],
    "tool_calls_parse_ok": true,
    "usage_completion_tokens": 108
  }
]
```
<!-- inkling-probe:effort-field:end -->

<!-- inkling-probe:follow-ups:start -->
## Follow-up probes

- Generated: `2026-07-16T01:48:17+00:00`
- Selected field representation: `top-level native reasoning_effort`
- High effort: `max`
- All requests were streamed with usage enabled, temperature 1, zero SDK retries, and strict concurrency 1.

### Streaming, tools, and reasoning-content batching

- Forced tool-call streams produced exactly one `submit_probe` call with a real call ID and the expected answer/checksum object: `yes` (5/5 requests succeeded)
- With tools present and `tool_choice=none`, reasoning arrived in exactly one delta at the first non-empty content delta in every successful sample: `yes`
- Forced tool-call records also retain whether reasoning shared the first answer-bearing (content or tool-call) delta; see raw records.

### `none` behavior

- Forced-tool usability: exact `submit_probe` calls remained usable at `none`: `yes`; reasoning tokens were <=5 in every successful forced-tool sample: `yes`.
- The separate textual probe omits both `tools` and `tool_choice` and requests a concise final marker, so its visible message content can test the folding claim.
- Textual folding classification: **not established**. `OBSERVED` requires every requested sample to succeed with content >= 200 chars and `reasoning_tokens<=5`; median content was `13` chars and median reasoning tokens were `0`.
- Folding was not established in the tool path, where zero visible content is legitimate, or by the textual threshold. The plan still treats `none` as non-canonical; that exclusion is plan-driven, not diagnostic-inferred.

### Separate max_tokens truncation stress comparison

The same `5000`-integer tool-call payload was requested at `max` for both caps. Only `confirmed_truncation` counts as truncation; request failures, successful model noncompliance, and inconclusive records are reported separately.
A complete sequence is shown in the complete column and categorized as `inconclusive` for the truncation hypothesis: it proves this payload completed, not that a larger payload could not truncate.

| max_tokens | Samples | Complete sequences | Confirmed truncation | Request failure | Model noncompliance | Inconclusive | Median completion tokens | Median reasoning tokens |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 8192 | 2 | 0 | 2 | 0 | 0 | 0 | N/A | N/A |
| 16384 | 2 | 2 | 0 | 0 | 0 | 2 | 14049 | 28 |

### Concurrency-1 rate limits and episode-style latency

- Requests observed across follow-ups: `30`
- HTTP 429 responses: `0`
- Retry-After values: `none observed`
- Completed two-turn tool episodes: `3/3`
- Configured inter-turn sleep: `0` seconds per episode (default `0`).
- Median two-turn episode wall time: `0.8` seconds, including the configured inter-turn sleep.
- Median summed request time: `0.8` seconds, excluding the inter-turn sleep and local handoff overhead.

| Episode | Turn 1 seconds | Turn 2 seconds | Request seconds | Wall seconds | Inter-turn sleep | Completed |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 0.4 | 0.5 | 0.9 | 0.9 | 0 | yes |
| 2 | 0.4 | 0.4 | 0.8 | 0.8 | 0 | yes |
| 3 | 0.4 | 0.5 | 0.8 | 0.8 | 0 | yes |

### Sweep recommendation

- **Diagnostic-inferred:** the controlled effort matrix observed approximately zero separate reasoning at `none` and roughly 80–160 reasoning tokens throughout the non-`none` levels, with no graded monotonic trend. That binary pattern supports sweeping `low`, `high`, and API `max` (the harness `xhigh` mapping) to sample the non-`none` operating region.
- **Integration-doc guidance:** `low` is the document's best single pick when only one configuration can be run.
- **Plan-driven:** exclude `none` from canonical runs and the leaderboard regardless of whether this follow-up establishes folded CoT. That exclusion comes from the project plan, not from the tool-path diagnostic.

### Raw follow-up records

```json
{
  "episodes": [
    {
      "completed_two_turns": true,
      "configured_inter_turn_sleep_secs": 0.0,
      "elapsed_secs": 0.9263304048217833,
      "request_elapsed_secs": 0.9261588798835874,
      "sample": 1,
      "turn_1": {
        "content_length": 0,
        "content_preview": "",
        "elapsed_secs": 0.4420607259962708,
        "error_body": null,
        "error_message": null,
        "error_type": null,
        "finish_reason": "tool_calls",
        "first_answer_chunk_index": 0,
        "first_content_chunk_index": null,
        "first_content_secs": null,
        "first_reasoning_chunk_index": null,
        "first_reasoning_secs": null,
        "first_tool_call_chunk_index": 0,
        "first_tool_call_secs": 0.44182738196104765,
        "http_status": 200,
        "label": "episode_turn_1_tool",
        "reasoning_content_length": 0,
        "reasoning_content_present": false,
        "reasoning_delta_count": 0,
        "reasoning_same_delta_as_first_answer": null,
        "reasoning_same_delta_as_first_content": null,
        "reasoning_tokens": 0,
        "request_breaking_400": false,
        "request_kwargs_sent": {
          "max_tokens": 16384,
          "messages": [
            {
              "content": "You are a two-turn tool-use diagnostic. Use lookup_probe. If its result says the code is ready, reply exactly: inkling-latency-v1 status: ready",
              "role": "system"
            },
            {
              "content": "Look up code inkling-latency-v1 and report its status.",
              "role": "user"
            }
          ],
          "model": "thinkingmachines/inkling",
          "reasoning_effort": "max",
          "stream": true,
          "stream_options": {
            "include_usage": true
          },
          "temperature": 1.0,
          "tool_choice": {
            "function": {
              "name": "lookup_probe"
            },
            "type": "function"
          },
          "tools": [
            {
              "function": {
                "description": "Look up a deterministic diagnostic code.",
                "name": "lookup_probe",
                "parameters": {
                  "additionalProperties": false,
                  "properties": {
                    "code": {
                      "type": "string"
                    }
                  },
                  "required": [
                    "code"
                  ],
                  "type": "object"
                }
              },
              "type": "function"
            }
          ]
        },
        "response_headers": {},
        "sample": 1,
        "started_utc": "2026-07-16T01:48:15+00:00",
        "tool_calls": [
          {
            "arguments_json_error": null,
            "arguments_json_valid": true,
            "arguments_length": 30,
            "arguments_preview": "{\"code\": \"inkling-latency-v1\"}",
            "id": "chatcmpl-tool-82b79562bcb74efe869ffb2f2852c4cc",
            "index": 0,
            "name": "lookup_probe",
            "type": "function"
          }
        ],
        "tool_calls_parse_error": null,
        "tool_calls_parse_ok": true,
        "usage_completion_tokens": 24
      },
      "turn_2": {
        "content_length": 32,
        "content_preview": "inkling-latency-v1 status: ready",
        "elapsed_secs": 0.4840981538873166,
        "error_body": null,
        "error_message": null,
        "error_type": null,
        "finish_reason": "stop",
        "first_answer_chunk_index": 0,
        "first_content_chunk_index": 0,
        "first_content_secs": 0.4838942459318787,
        "first_reasoning_chunk_index": 0,
        "first_reasoning_secs": 0.4838933749124408,
        "first_tool_call_chunk_index": null,
        "first_tool_call_secs": null,
        "http_status": 200,
        "label": "episode_turn_2_answer",
        "reasoning_content_length": 91,
        "reasoning_content_present": true,
        "reasoning_delta_count": 1,
        "reasoning_same_delta_as_first_answer": true,
        "reasoning_same_delta_as_first_content": true,
        "reasoning_tokens": 19,
        "request_breaking_400": false,
        "request_kwargs_sent": {
          "max_tokens": 16384,
          "messages": [
            {
              "content": "You are a two-turn tool-use diagnostic. Use lookup_probe. If its result says the code is ready, reply exactly: inkling-latency-v1 status: ready",
              "role": "system"
            },
            {
              "content": "Look up code inkling-latency-v1 and report its status.",
              "role": "user"
            },
            {
              "content": null,
              "role": "assistant",
              "tool_calls": [
                {
                  "function": {
                    "arguments": "{\"code\": \"inkling-latency-v1\"}",
                    "name": "lookup_probe"
                  },
                  "id": "chatcmpl-tool-82b79562bcb74efe869ffb2f2852c4cc",
                  "type": "function"
                }
              ]
            },
            {
              "content": "{\"code\": \"inkling-latency-v1\", \"source\": \"deterministic-probe\", \"status\": \"ready\"}",
              "role": "tool",
              "tool_call_id": "chatcmpl-tool-82b79562bcb74efe869ffb2f2852c4cc"
            }
          ],
          "model": "thinkingmachines/inkling",
          "reasoning_effort": "max",
          "stream": true,
          "stream_options": {
            "include_usage": true
          },
          "temperature": 1.0,
          "tool_choice": "none",
          "tools": [
            {
              "function": {
                "description": "Look up a deterministic diagnostic code.",
                "name": "lookup_probe",
                "parameters": {
                  "additionalProperties": false,
                  "properties": {
                    "code": {
                      "type": "string"
                    }
                  },
                  "required": [
                    "code"
                  ],
                  "type": "object"
                }
              },
              "type": "function"
            }
          ]
        },
        "response_headers": {},
        "sample": 1,
        "started_utc": "2026-07-16T01:48:15+00:00",
        "tool_calls": [],
        "tool_calls_parse_error": null,
        "tool_calls_parse_ok": false,
        "usage_completion_tokens": 36
      },
      "turn_2_expected_answer_ok": true
    },
    {
      "completed_two_turns": true,
      "configured_inter_turn_sleep_secs": 0.0,
      "elapsed_secs": 0.8022544081322849,
      "request_elapsed_secs": 0.8020919291302562,
      "sample": 2,
      "turn_1": {
        "content_length": 0,
        "content_preview": "",
        "elapsed_secs": 0.363500984152779,
        "error_body": null,
        "error_message": null,
        "error_type": null,
        "finish_reason": "tool_calls",
        "first_answer_chunk_index": 0,
        "first_content_chunk_index": null,
        "first_content_secs": null,
        "first_reasoning_chunk_index": null,
        "first_reasoning_secs": null,
        "first_tool_call_chunk_index": 0,
        "first_tool_call_secs": 0.36324695218354464,
        "http_status": 200,
        "label": "episode_turn_1_tool",
        "reasoning_content_length": 0,
        "reasoning_content_present": false,
        "reasoning_delta_count": 0,
        "reasoning_same_delta_as_first_answer": null,
        "reasoning_same_delta_as_first_content": null,
        "reasoning_tokens": 0,
        "request_breaking_400": false,
        "request_kwargs_sent": {
          "max_tokens": 16384,
          "messages": [
            {
              "content": "You are a two-turn tool-use diagnostic. Use lookup_probe. If its result says the code is ready, reply exactly: inkling-latency-v1 status: ready",
              "role": "system"
            },
            {
              "content": "Look up code inkling-latency-v1 and report its status.",
              "role": "user"
            }
          ],
          "model": "thinkingmachines/inkling",
          "reasoning_effort": "max",
          "stream": true,
          "stream_options": {
            "include_usage": true
          },
          "temperature": 1.0,
          "tool_choice": {
            "function": {
              "name": "lookup_probe"
            },
            "type": "function"
          },
          "tools": [
            {
              "function": {
                "description": "Look up a deterministic diagnostic code.",
                "name": "lookup_probe",
                "parameters": {
                  "additionalProperties": false,
                  "properties": {
                    "code": {
                      "type": "string"
                    }
                  },
                  "required": [
                    "code"
                  ],
                  "type": "object"
                }
              },
              "type": "function"
            }
          ]
        },
        "response_headers": {},
        "sample": 2,
        "started_utc": "2026-07-16T01:48:16+00:00",
        "tool_calls": [
          {
            "arguments_json_error": null,
            "arguments_json_valid": true,
            "arguments_length": 30,
            "arguments_preview": "{\"code\": \"inkling-latency-v1\"}",
            "id": "chatcmpl-tool-a5a3f5b0f9734dfb9767ceef26a9dd01",
            "index": 0,
            "name": "lookup_probe",
            "type": "function"
          }
        ],
        "tool_calls_parse_error": null,
        "tool_calls_parse_ok": true,
        "usage_completion_tokens": 24
      },
      "turn_2": {
        "content_length": 32,
        "content_preview": "inkling-latency-v1 status: ready",
        "elapsed_secs": 0.4385909449774772,
        "error_body": null,
        "error_message": null,
        "error_type": null,
        "finish_reason": "stop",
        "first_answer_chunk_index": 0,
        "first_content_chunk_index": 0,
        "first_content_secs": 0.436795735033229,
        "first_reasoning_chunk_index": 0,
        "first_reasoning_secs": 0.43679437204264104,
        "first_tool_call_chunk_index": null,
        "first_tool_call_secs": null,
        "http_status": 200,
        "label": "episode_turn_2_answer",
        "reasoning_content_length": 94,
        "reasoning_content_present": true,
        "reasoning_delta_count": 1,
        "reasoning_same_delta_as_first_answer": true,
        "reasoning_same_delta_as_first_content": true,
        "reasoning_tokens": 20,
        "request_breaking_400": false,
        "request_kwargs_sent": {
          "max_tokens": 16384,
          "messages": [
            {
              "content": "You are a two-turn tool-use diagnostic. Use lookup_probe. If its result says the code is ready, reply exactly: inkling-latency-v1 status: ready",
              "role": "system"
            },
            {
              "content": "Look up code inkling-latency-v1 and report its status.",
              "role": "user"
            },
            {
              "content": null,
              "role": "assistant",
              "tool_calls": [
                {
                  "function": {
                    "arguments": "{\"code\": \"inkling-latency-v1\"}",
                    "name": "lookup_probe"
                  },
                  "id": "chatcmpl-tool-a5a3f5b0f9734dfb9767ceef26a9dd01",
                  "type": "function"
                }
              ]
            },
            {
              "content": "{\"code\": \"inkling-latency-v1\", \"source\": \"deterministic-probe\", \"status\": \"ready\"}",
              "role": "tool",
              "tool_call_id": "chatcmpl-tool-a5a3f5b0f9734dfb9767ceef26a9dd01"
            }
          ],
          "model": "thinkingmachines/inkling",
          "reasoning_effort": "max",
          "stream": true,
          "stream_options": {
            "include_usage": true
          },
          "temperature": 1.0,
          "tool_choice": "none",
          "tools": [
            {
              "function": {
                "description": "Look up a deterministic diagnostic code.",
                "name": "lookup_probe",
                "parameters": {
                  "additionalProperties": false,
                  "properties": {
                    "code": {
                      "type": "string"
                    }
                  },
                  "required": [
                    "code"
                  ],
                  "type": "object"
                }
              },
              "type": "function"
            }
          ]
        },
        "response_headers": {},
        "sample": 2,
        "started_utc": "2026-07-16T01:48:16+00:00",
        "tool_calls": [],
        "tool_calls_parse_error": null,
        "tool_calls_parse_ok": false,
        "usage_completion_tokens": 37
      },
      "turn_2_expected_answer_ok": true
    },
    {
      "completed_two_turns": true,
      "configured_inter_turn_sleep_secs": 0.0,
      "elapsed_secs": 0.8351406250149012,
      "request_elapsed_secs": 0.8349744789302349,
      "sample": 3,
      "turn_1": {
        "content_length": 0,
        "content_preview": "",
        "elapsed_secs": 0.3637621710076928,
        "error_body": null,
        "error_message": null,
        "error_type": null,
        "finish_reason": "tool_calls",
        "first_answer_chunk_index": 0,
        "first_content_chunk_index": null,
        "first_content_secs": null,
        "first_reasoning_chunk_index": null,
        "first_reasoning_secs": null,
        "first_tool_call_chunk_index": 0,
        "first_tool_call_secs": 0.36352611309848726,
        "http_status": 200,
        "label": "episode_turn_1_tool",
        "reasoning_content_length": 0,
        "reasoning_content_present": false,
        "reasoning_delta_count": 0,
        "reasoning_same_delta_as_first_answer": null,
        "reasoning_same_delta_as_first_content": null,
        "reasoning_tokens": 0,
        "request_breaking_400": false,
        "request_kwargs_sent": {
          "max_tokens": 16384,
          "messages": [
            {
              "content": "You are a two-turn tool-use diagnostic. Use lookup_probe. If its result says the code is ready, reply exactly: inkling-latency-v1 status: ready",
              "role": "system"
            },
            {
              "content": "Look up code inkling-latency-v1 and report its status.",
              "role": "user"
            }
          ],
          "model": "thinkingmachines/inkling",
          "reasoning_effort": "max",
          "stream": true,
          "stream_options": {
            "include_usage": true
          },
          "temperature": 1.0,
          "tool_choice": {
            "function": {
              "name": "lookup_probe"
            },
            "type": "function"
          },
          "tools": [
            {
              "function": {
                "description": "Look up a deterministic diagnostic code.",
                "name": "lookup_probe",
                "parameters": {
                  "additionalProperties": false,
                  "properties": {
                    "code": {
                      "type": "string"
                    }
                  },
                  "required": [
                    "code"
                  ],
                  "type": "object"
                }
              },
              "type": "function"
            }
          ]
        },
        "response_headers": {},
        "sample": 3,
        "started_utc": "2026-07-16T01:48:17+00:00",
        "tool_calls": [
          {
            "arguments_json_error": null,
            "arguments_json_valid": true,
            "arguments_length": 30,
            "arguments_preview": "{\"code\": \"inkling-latency-v1\"}",
            "id": "chatcmpl-tool-2a706c2928a04fe5ad08ece45abf93bf",
            "index": 0,
            "name": "lookup_probe",
            "type": "function"
          }
        ],
        "tool_calls_parse_error": null,
        "tool_calls_parse_ok": true,
        "usage_completion_tokens": 24
      },
      "turn_2": {
        "content_length": 32,
        "content_preview": "inkling-latency-v1 status: ready",
        "elapsed_secs": 0.4712123079225421,
        "error_body": null,
        "error_message": null,
        "error_type": null,
        "finish_reason": "stop",
        "first_answer_chunk_index": 0,
        "first_content_chunk_index": 0,
        "first_content_secs": 0.47100019501522183,
        "first_reasoning_chunk_index": 0,
        "first_reasoning_secs": 0.4709992930293083,
        "first_tool_call_chunk_index": null,
        "first_tool_call_secs": null,
        "http_status": 200,
        "label": "episode_turn_2_answer",
        "reasoning_content_length": 103,
        "reasoning_content_present": true,
        "reasoning_delta_count": 1,
        "reasoning_same_delta_as_first_answer": true,
        "reasoning_same_delta_as_first_content": true,
        "reasoning_tokens": 26,
        "request_breaking_400": false,
        "request_kwargs_sent": {
          "max_tokens": 16384,
          "messages": [
            {
              "content": "You are a two-turn tool-use diagnostic. Use lookup_probe. If its result says the code is ready, reply exactly: inkling-latency-v1 status: ready",
              "role": "system"
            },
            {
              "content": "Look up code inkling-latency-v1 and report its status.",
              "role": "user"
            },
            {
              "content": null,
              "role": "assistant",
              "tool_calls": [
                {
                  "function": {
                    "arguments": "{\"code\": \"inkling-latency-v1\"}",
                    "name": "lookup_probe"
                  },
                  "id": "chatcmpl-tool-2a706c2928a04fe5ad08ece45abf93bf",
                  "type": "function"
                }
              ]
            },
            {
              "content": "{\"code\": \"inkling-latency-v1\", \"source\": \"deterministic-probe\", \"status\": \"ready\"}",
              "role": "tool",
              "tool_call_id": "chatcmpl-tool-2a706c2928a04fe5ad08ece45abf93bf"
            }
          ],
          "model": "thinkingmachines/inkling",
          "reasoning_effort": "max",
          "stream": true,
          "stream_options": {
            "include_usage": true
          },
          "temperature": 1.0,
          "tool_choice": "none",
          "tools": [
            {
              "function": {
                "description": "Look up a deterministic diagnostic code.",
                "name": "lookup_probe",
                "parameters": {
                  "additionalProperties": false,
                  "properties": {
                    "code": {
                      "type": "string"
                    }
                  },
                  "required": [
                    "code"
                  ],
                  "type": "object"
                }
              },
              "type": "function"
            }
          ]
        },
        "response_headers": {},
        "sample": 3,
        "started_utc": "2026-07-16T01:48:17+00:00",
        "tool_calls": [],
        "tool_calls_parse_error": null,
        "tool_calls_parse_ok": false,
        "usage_completion_tokens": 43
      },
      "turn_2_expected_answer_ok": true
    }
  ],
  "none_forced_tool": [
    {
      "content_length": 0,
      "content_preview": "",
      "elapsed_secs": 0.382547867950052,
      "error_body": null,
      "error_message": null,
      "error_type": null,
      "finish_reason": "tool_calls",
      "first_answer_chunk_index": 0,
      "first_content_chunk_index": null,
      "first_content_secs": null,
      "first_reasoning_chunk_index": null,
      "first_reasoning_secs": null,
      "first_tool_call_chunk_index": 0,
      "first_tool_call_secs": 0.38215079391375184,
      "http_status": 200,
      "label": "none_forced_tool_usability",
      "reasoning_content_length": 0,
      "reasoning_content_present": false,
      "reasoning_delta_count": 0,
      "reasoning_same_delta_as_first_answer": null,
      "reasoning_same_delta_as_first_content": null,
      "reasoning_tokens": 0,
      "request_breaking_400": false,
      "request_kwargs_sent": {
        "max_tokens": 16384,
        "messages": [
          {
            "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
            "role": "system"
          },
          {
            "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
            "role": "user"
          }
        ],
        "model": "thinkingmachines/inkling",
        "reasoning_effort": "none",
        "stream": true,
        "stream_options": {
          "include_usage": true
        },
        "temperature": 1.0,
        "tool_choice": {
          "function": {
            "name": "submit_probe"
          },
          "type": "function"
        },
        "tools": [
          {
            "function": {
              "description": "Submit the answer for the controlled Inkling probe.",
              "name": "submit_probe",
              "parameters": {
                "additionalProperties": false,
                "properties": {
                  "answer": {
                    "type": "integer"
                  },
                  "checksum": {
                    "type": "string"
                  }
                },
                "required": [
                  "answer",
                  "checksum"
                ],
                "type": "object"
              }
            },
            "type": "function"
          }
        ]
      },
      "response_headers": {},
      "sample": 1,
      "started_utc": "2026-07-16T01:43:00+00:00",
      "tool_calls": [
        {
          "arguments_json_error": null,
          "arguments_json_valid": true,
          "arguments_length": 53,
          "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
          "id": "chatcmpl-tool-c79cb88bce8541c99003872b76c3ea3a",
          "index": 0,
          "name": "submit_probe",
          "type": "function"
        }
      ],
      "tool_calls_parse_error": null,
      "tool_calls_parse_ok": true,
      "usage_completion_tokens": 27
    },
    {
      "content_length": 0,
      "content_preview": "",
      "elapsed_secs": 0.3736436648759991,
      "error_body": null,
      "error_message": null,
      "error_type": null,
      "finish_reason": "tool_calls",
      "first_answer_chunk_index": 0,
      "first_content_chunk_index": null,
      "first_content_secs": null,
      "first_reasoning_chunk_index": null,
      "first_reasoning_secs": null,
      "first_tool_call_chunk_index": 0,
      "first_tool_call_secs": 0.3734566499479115,
      "http_status": 200,
      "label": "none_forced_tool_usability",
      "reasoning_content_length": 0,
      "reasoning_content_present": false,
      "reasoning_delta_count": 0,
      "reasoning_same_delta_as_first_answer": null,
      "reasoning_same_delta_as_first_content": null,
      "reasoning_tokens": 0,
      "request_breaking_400": false,
      "request_kwargs_sent": {
        "max_tokens": 16384,
        "messages": [
          {
            "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
            "role": "system"
          },
          {
            "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
            "role": "user"
          }
        ],
        "model": "thinkingmachines/inkling",
        "reasoning_effort": "none",
        "stream": true,
        "stream_options": {
          "include_usage": true
        },
        "temperature": 1.0,
        "tool_choice": {
          "function": {
            "name": "submit_probe"
          },
          "type": "function"
        },
        "tools": [
          {
            "function": {
              "description": "Submit the answer for the controlled Inkling probe.",
              "name": "submit_probe",
              "parameters": {
                "additionalProperties": false,
                "properties": {
                  "answer": {
                    "type": "integer"
                  },
                  "checksum": {
                    "type": "string"
                  }
                },
                "required": [
                  "answer",
                  "checksum"
                ],
                "type": "object"
              }
            },
            "type": "function"
          }
        ]
      },
      "response_headers": {},
      "sample": 2,
      "started_utc": "2026-07-16T01:43:01+00:00",
      "tool_calls": [
        {
          "arguments_json_error": null,
          "arguments_json_valid": true,
          "arguments_length": 53,
          "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
          "id": "chatcmpl-tool-57352300e469465099b9a6cab8898f03",
          "index": 0,
          "name": "submit_probe",
          "type": "function"
        }
      ],
      "tool_calls_parse_error": null,
      "tool_calls_parse_ok": true,
      "usage_completion_tokens": 27
    },
    {
      "content_length": 0,
      "content_preview": "",
      "elapsed_secs": 0.37787255784496665,
      "error_body": null,
      "error_message": null,
      "error_type": null,
      "finish_reason": "tool_calls",
      "first_answer_chunk_index": 0,
      "first_content_chunk_index": null,
      "first_content_secs": null,
      "first_reasoning_chunk_index": null,
      "first_reasoning_secs": null,
      "first_tool_call_chunk_index": 0,
      "first_tool_call_secs": 0.37766607478260994,
      "http_status": 200,
      "label": "none_forced_tool_usability",
      "reasoning_content_length": 0,
      "reasoning_content_present": false,
      "reasoning_delta_count": 0,
      "reasoning_same_delta_as_first_answer": null,
      "reasoning_same_delta_as_first_content": null,
      "reasoning_tokens": 0,
      "request_breaking_400": false,
      "request_kwargs_sent": {
        "max_tokens": 16384,
        "messages": [
          {
            "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
            "role": "system"
          },
          {
            "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
            "role": "user"
          }
        ],
        "model": "thinkingmachines/inkling",
        "reasoning_effort": "none",
        "stream": true,
        "stream_options": {
          "include_usage": true
        },
        "temperature": 1.0,
        "tool_choice": {
          "function": {
            "name": "submit_probe"
          },
          "type": "function"
        },
        "tools": [
          {
            "function": {
              "description": "Submit the answer for the controlled Inkling probe.",
              "name": "submit_probe",
              "parameters": {
                "additionalProperties": false,
                "properties": {
                  "answer": {
                    "type": "integer"
                  },
                  "checksum": {
                    "type": "string"
                  }
                },
                "required": [
                  "answer",
                  "checksum"
                ],
                "type": "object"
              }
            },
            "type": "function"
          }
        ]
      },
      "response_headers": {},
      "sample": 3,
      "started_utc": "2026-07-16T01:43:01+00:00",
      "tool_calls": [
        {
          "arguments_json_error": null,
          "arguments_json_valid": true,
          "arguments_length": 53,
          "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
          "id": "chatcmpl-tool-7151f25aa5a140f4b7dfc7ebf9ba9fc4",
          "index": 0,
          "name": "submit_probe",
          "type": "function"
        }
      ],
      "tool_calls_parse_error": null,
      "tool_calls_parse_ok": true,
      "usage_completion_tokens": 27
    },
    {
      "content_length": 0,
      "content_preview": "",
      "elapsed_secs": 0.37506633903831244,
      "error_body": null,
      "error_message": null,
      "error_type": null,
      "finish_reason": "tool_calls",
      "first_answer_chunk_index": 0,
      "first_content_chunk_index": null,
      "first_content_secs": null,
      "first_reasoning_chunk_index": null,
      "first_reasoning_secs": null,
      "first_tool_call_chunk_index": 0,
      "first_tool_call_secs": 0.37482756515964866,
      "http_status": 200,
      "label": "none_forced_tool_usability",
      "reasoning_content_length": 0,
      "reasoning_content_present": false,
      "reasoning_delta_count": 0,
      "reasoning_same_delta_as_first_answer": null,
      "reasoning_same_delta_as_first_content": null,
      "reasoning_tokens": 0,
      "request_breaking_400": false,
      "request_kwargs_sent": {
        "max_tokens": 16384,
        "messages": [
          {
            "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
            "role": "system"
          },
          {
            "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
            "role": "user"
          }
        ],
        "model": "thinkingmachines/inkling",
        "reasoning_effort": "none",
        "stream": true,
        "stream_options": {
          "include_usage": true
        },
        "temperature": 1.0,
        "tool_choice": {
          "function": {
            "name": "submit_probe"
          },
          "type": "function"
        },
        "tools": [
          {
            "function": {
              "description": "Submit the answer for the controlled Inkling probe.",
              "name": "submit_probe",
              "parameters": {
                "additionalProperties": false,
                "properties": {
                  "answer": {
                    "type": "integer"
                  },
                  "checksum": {
                    "type": "string"
                  }
                },
                "required": [
                  "answer",
                  "checksum"
                ],
                "type": "object"
              }
            },
            "type": "function"
          }
        ]
      },
      "response_headers": {},
      "sample": 4,
      "started_utc": "2026-07-16T01:43:01+00:00",
      "tool_calls": [
        {
          "arguments_json_error": null,
          "arguments_json_valid": true,
          "arguments_length": 53,
          "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
          "id": "chatcmpl-tool-2bd8378937454007bf113b0960c6ecd0",
          "index": 0,
          "name": "submit_probe",
          "type": "function"
        }
      ],
      "tool_calls_parse_error": null,
      "tool_calls_parse_ok": true,
      "usage_completion_tokens": 27
    },
    {
      "content_length": 0,
      "content_preview": "",
      "elapsed_secs": 0.3715659291483462,
      "error_body": null,
      "error_message": null,
      "error_type": null,
      "finish_reason": "tool_calls",
      "first_answer_chunk_index": 0,
      "first_content_chunk_index": null,
      "first_content_secs": null,
      "first_reasoning_chunk_index": null,
      "first_reasoning_secs": null,
      "first_tool_call_chunk_index": 0,
      "first_tool_call_secs": 0.3713409211486578,
      "http_status": 200,
      "label": "none_forced_tool_usability",
      "reasoning_content_length": 0,
      "reasoning_content_present": false,
      "reasoning_delta_count": 0,
      "reasoning_same_delta_as_first_answer": null,
      "reasoning_same_delta_as_first_content": null,
      "reasoning_tokens": 0,
      "request_breaking_400": false,
      "request_kwargs_sent": {
        "max_tokens": 16384,
        "messages": [
          {
            "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
            "role": "system"
          },
          {
            "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
            "role": "user"
          }
        ],
        "model": "thinkingmachines/inkling",
        "reasoning_effort": "none",
        "stream": true,
        "stream_options": {
          "include_usage": true
        },
        "temperature": 1.0,
        "tool_choice": {
          "function": {
            "name": "submit_probe"
          },
          "type": "function"
        },
        "tools": [
          {
            "function": {
              "description": "Submit the answer for the controlled Inkling probe.",
              "name": "submit_probe",
              "parameters": {
                "additionalProperties": false,
                "properties": {
                  "answer": {
                    "type": "integer"
                  },
                  "checksum": {
                    "type": "string"
                  }
                },
                "required": [
                  "answer",
                  "checksum"
                ],
                "type": "object"
              }
            },
            "type": "function"
          }
        ]
      },
      "response_headers": {},
      "sample": 5,
      "started_utc": "2026-07-16T01:43:02+00:00",
      "tool_calls": [
        {
          "arguments_json_error": null,
          "arguments_json_valid": true,
          "arguments_length": 53,
          "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
          "id": "chatcmpl-tool-0743bb35533c43eeb7fd0056769a1b58",
          "index": 0,
          "name": "submit_probe",
          "type": "function"
        }
      ],
      "tool_calls_parse_error": null,
      "tool_calls_parse_ok": true,
      "usage_completion_tokens": 27
    }
  ],
  "none_textual": [
    {
      "content_length": 13,
      "content_preview": "FINAL: 374101",
      "elapsed_secs": 0.2994684230070561,
      "error_body": null,
      "error_message": null,
      "error_type": null,
      "finish_reason": "stop",
      "first_answer_chunk_index": 0,
      "first_content_chunk_index": 0,
      "first_content_secs": 0.26154131116345525,
      "first_reasoning_chunk_index": null,
      "first_reasoning_secs": null,
      "first_tool_call_chunk_index": null,
      "first_tool_call_secs": null,
      "folded_cot_evidence": false,
      "http_status": 200,
      "label": "none_textual_folded_content",
      "reasoning_content_length": 0,
      "reasoning_content_present": false,
      "reasoning_delta_count": 0,
      "reasoning_same_delta_as_first_answer": null,
      "reasoning_same_delta_as_first_content": null,
      "reasoning_tokens": 0,
      "request_breaking_400": false,
      "request_kwargs_sent": {
        "max_tokens": 16384,
        "messages": [
          {
            "content": "Solve the arithmetic carefully, but return only `FINAL: <integer>` with no explanation or intermediate work.",
            "role": "system"
          },
          {
            "content": "Compute ((137 * 149) + (173 * 181) - (19 * 23)) * 7. Return only the requested final marker.",
            "role": "user"
          }
        ],
        "model": "thinkingmachines/inkling",
        "reasoning_effort": "none",
        "stream": true,
        "stream_options": {
          "include_usage": true
        },
        "temperature": 1.0
      },
      "response_headers": {},
      "sample": 1,
      "started_utc": "2026-07-16T01:43:02+00:00",
      "tool_calls": [],
      "tool_calls_parse_error": null,
      "tool_calls_parse_ok": false,
      "usage_completion_tokens": 9
    },
    {
      "content_length": 13,
      "content_preview": "FINAL: 231259",
      "elapsed_secs": 0.23653973103500903,
      "error_body": null,
      "error_message": null,
      "error_type": null,
      "finish_reason": "stop",
      "first_answer_chunk_index": 0,
      "first_content_chunk_index": 0,
      "first_content_secs": 0.1972296021413058,
      "first_reasoning_chunk_index": null,
      "first_reasoning_secs": null,
      "first_tool_call_chunk_index": null,
      "first_tool_call_secs": null,
      "folded_cot_evidence": false,
      "http_status": 200,
      "label": "none_textual_folded_content",
      "reasoning_content_length": 0,
      "reasoning_content_present": false,
      "reasoning_delta_count": 0,
      "reasoning_same_delta_as_first_answer": null,
      "reasoning_same_delta_as_first_content": null,
      "reasoning_tokens": 0,
      "request_breaking_400": false,
      "request_kwargs_sent": {
        "max_tokens": 16384,
        "messages": [
          {
            "content": "Solve the arithmetic carefully, but return only `FINAL: <integer>` with no explanation or intermediate work.",
            "role": "system"
          },
          {
            "content": "Compute ((137 * 149) + (173 * 181) - (19 * 23)) * 7. Return only the requested final marker.",
            "role": "user"
          }
        ],
        "model": "thinkingmachines/inkling",
        "reasoning_effort": "none",
        "stream": true,
        "stream_options": {
          "include_usage": true
        },
        "temperature": 1.0
      },
      "response_headers": {},
      "sample": 2,
      "started_utc": "2026-07-16T01:43:03+00:00",
      "tool_calls": [],
      "tool_calls_parse_error": null,
      "tool_calls_parse_ok": false,
      "usage_completion_tokens": 9
    },
    {
      "content_length": 12,
      "content_preview": "FINAL: 28147",
      "elapsed_secs": 0.24175187083892524,
      "error_body": null,
      "error_message": null,
      "error_type": null,
      "finish_reason": "stop",
      "first_answer_chunk_index": 0,
      "first_content_chunk_index": 0,
      "first_content_secs": 0.20654801186174154,
      "first_reasoning_chunk_index": null,
      "first_reasoning_secs": null,
      "first_tool_call_chunk_index": null,
      "first_tool_call_secs": null,
      "folded_cot_evidence": false,
      "http_status": 200,
      "label": "none_textual_folded_content",
      "reasoning_content_length": 0,
      "reasoning_content_present": false,
      "reasoning_delta_count": 0,
      "reasoning_same_delta_as_first_answer": null,
      "reasoning_same_delta_as_first_content": null,
      "reasoning_tokens": 0,
      "request_breaking_400": false,
      "request_kwargs_sent": {
        "max_tokens": 16384,
        "messages": [
          {
            "content": "Solve the arithmetic carefully, but return only `FINAL: <integer>` with no explanation or intermediate work.",
            "role": "system"
          },
          {
            "content": "Compute ((137 * 149) + (173 * 181) - (19 * 23)) * 7. Return only the requested final marker.",
            "role": "user"
          }
        ],
        "model": "thinkingmachines/inkling",
        "reasoning_effort": "none",
        "stream": true,
        "stream_options": {
          "include_usage": true
        },
        "temperature": 1.0
      },
      "response_headers": {},
      "sample": 3,
      "started_utc": "2026-07-16T01:43:03+00:00",
      "tool_calls": [],
      "tool_calls_parse_error": null,
      "tool_calls_parse_ok": false,
      "usage_completion_tokens": 9
    },
    {
      "content_length": 13,
      "content_preview": "FINAL: 246701",
      "elapsed_secs": 0.24576769908890128,
      "error_body": null,
      "error_message": null,
      "error_type": null,
      "finish_reason": "stop",
      "first_answer_chunk_index": 0,
      "first_content_chunk_index": 0,
      "first_content_secs": 0.20798242604359984,
      "first_reasoning_chunk_index": null,
      "first_reasoning_secs": null,
      "first_tool_call_chunk_index": null,
      "first_tool_call_secs": null,
      "folded_cot_evidence": false,
      "http_status": 200,
      "label": "none_textual_folded_content",
      "reasoning_content_length": 0,
      "reasoning_content_present": false,
      "reasoning_delta_count": 0,
      "reasoning_same_delta_as_first_answer": null,
      "reasoning_same_delta_as_first_content": null,
      "reasoning_tokens": 0,
      "request_breaking_400": false,
      "request_kwargs_sent": {
        "max_tokens": 16384,
        "messages": [
          {
            "content": "Solve the arithmetic carefully, but return only `FINAL: <integer>` with no explanation or intermediate work.",
            "role": "system"
          },
          {
            "content": "Compute ((137 * 149) + (173 * 181) - (19 * 23)) * 7. Return only the requested final marker.",
            "role": "user"
          }
        ],
        "model": "thinkingmachines/inkling",
        "reasoning_effort": "none",
        "stream": true,
        "stream_options": {
          "include_usage": true
        },
        "temperature": 1.0
      },
      "response_headers": {},
      "sample": 4,
      "started_utc": "2026-07-16T01:43:03+00:00",
      "tool_calls": [],
      "tool_calls_parse_error": null,
      "tool_calls_parse_ok": false,
      "usage_completion_tokens": 9
    },
    {
      "content_length": 13,
      "content_preview": "FINAL: 231469",
      "elapsed_secs": 0.24289740691892803,
      "error_body": null,
      "error_message": null,
      "error_type": null,
      "finish_reason": "stop",
      "first_answer_chunk_index": 0,
      "first_content_chunk_index": 0,
      "first_content_secs": 0.20324372593313456,
      "first_reasoning_chunk_index": null,
      "first_reasoning_secs": null,
      "first_tool_call_chunk_index": null,
      "first_tool_call_secs": null,
      "folded_cot_evidence": false,
      "http_status": 200,
      "label": "none_textual_folded_content",
      "reasoning_content_length": 0,
      "reasoning_content_present": false,
      "reasoning_delta_count": 0,
      "reasoning_same_delta_as_first_answer": null,
      "reasoning_same_delta_as_first_content": null,
      "reasoning_tokens": 0,
      "request_breaking_400": false,
      "request_kwargs_sent": {
        "max_tokens": 16384,
        "messages": [
          {
            "content": "Solve the arithmetic carefully, but return only `FINAL: <integer>` with no explanation or intermediate work.",
            "role": "system"
          },
          {
            "content": "Compute ((137 * 149) + (173 * 181) - (19 * 23)) * 7. Return only the requested final marker.",
            "role": "user"
          }
        ],
        "model": "thinkingmachines/inkling",
        "reasoning_effort": "none",
        "stream": true,
        "stream_options": {
          "include_usage": true
        },
        "temperature": 1.0
      },
      "response_headers": {},
      "sample": 5,
      "started_utc": "2026-07-16T01:43:03+00:00",
      "tool_calls": [],
      "tool_calls_parse_error": null,
      "tool_calls_parse_ok": false,
      "usage_completion_tokens": 9
    }
  ],
  "reasoning_batch_with_tools": [
    {
      "content_length": 137,
      "content_preview": "2416 ends in 6, and any integer ending in an even digit is divisible by 2. Specifically, 2416 \u00f7 2 = 1208 with no remainder, so it\u2019s even.",
      "elapsed_secs": 0.8770324799697846,
      "error_body": null,
      "error_message": null,
      "error_type": null,
      "finish_reason": "stop",
      "first_answer_chunk_index": 0,
      "first_content_chunk_index": 0,
      "first_content_secs": 0.8768536611460149,
      "first_reasoning_chunk_index": 0,
      "first_reasoning_secs": 0.8768519370350987,
      "first_tool_call_chunk_index": null,
      "first_tool_call_secs": null,
      "http_status": 200,
      "label": "reasoning_batch_with_tools",
      "reasoning_content_length": 179,
      "reasoning_content_present": true,
      "reasoning_delta_count": 1,
      "reasoning_same_delta_as_first_answer": true,
      "reasoning_same_delta_as_first_content": true,
      "reasoning_tokens": 45,
      "request_breaking_400": false,
      "request_kwargs_sent": {
        "max_tokens": 16384,
        "messages": [
          {
            "content": "You are a concise streaming diagnostic.",
            "role": "system"
          },
          {
            "content": "The request contains tools, but do not call one. In two short sentences, explain why 2416 is even.",
            "role": "user"
          }
        ],
        "model": "thinkingmachines/inkling",
        "reasoning_effort": "max",
        "stream": true,
        "stream_options": {
          "include_usage": true
        },
        "temperature": 1.0,
        "tool_choice": "none",
        "tools": [
          {
            "function": {
              "description": "Submit the answer for the controlled Inkling probe.",
              "name": "submit_probe",
              "parameters": {
                "additionalProperties": false,
                "properties": {
                  "answer": {
                    "type": "integer"
                  },
                  "checksum": {
                    "type": "string"
                  }
                },
                "required": [
                  "answer",
                  "checksum"
                ],
                "type": "object"
              }
            },
            "type": "function"
          }
        ]
      },
      "response_headers": {},
      "sample": 1,
      "started_utc": "2026-07-16T01:42:56+00:00",
      "tool_calls": [],
      "tool_calls_parse_error": null,
      "tool_calls_parse_ok": false,
      "usage_completion_tokens": 95
    },
    {
      "content_length": 109,
      "content_preview": "2416 ends in 6, so it\u2019s divisible by 2. Specifically, 2416 \u00f7 2 = 1208 with no remainder, which makes it even.",
      "elapsed_secs": 0.7957292459905148,
      "error_body": null,
      "error_message": null,
      "error_type": null,
      "finish_reason": "stop",
      "first_answer_chunk_index": 0,
      "first_content_chunk_index": 0,
      "first_content_secs": 0.7955323220230639,
      "first_reasoning_chunk_index": 0,
      "first_reasoning_secs": 0.7955309490207583,
      "first_tool_call_chunk_index": null,
      "first_tool_call_secs": null,
      "http_status": 200,
      "label": "reasoning_batch_with_tools",
      "reasoning_content_length": 177,
      "reasoning_content_present": true,
      "reasoning_delta_count": 1,
      "reasoning_same_delta_as_first_answer": true,
      "reasoning_same_delta_as_first_content": true,
      "reasoning_tokens": 49,
      "request_breaking_400": false,
      "request_kwargs_sent": {
        "max_tokens": 16384,
        "messages": [
          {
            "content": "You are a concise streaming diagnostic.",
            "role": "system"
          },
          {
            "content": "The request contains tools, but do not call one. In two short sentences, explain why 2416 is even.",
            "role": "user"
          }
        ],
        "model": "thinkingmachines/inkling",
        "reasoning_effort": "max",
        "stream": true,
        "stream_options": {
          "include_usage": true
        },
        "temperature": 1.0,
        "tool_choice": "none",
        "tools": [
          {
            "function": {
              "description": "Submit the answer for the controlled Inkling probe.",
              "name": "submit_probe",
              "parameters": {
                "additionalProperties": false,
                "properties": {
                  "answer": {
                    "type": "integer"
                  },
                  "checksum": {
                    "type": "string"
                  }
                },
                "required": [
                  "answer",
                  "checksum"
                ],
                "type": "object"
              }
            },
            "type": "function"
          }
        ]
      },
      "response_headers": {},
      "sample": 2,
      "started_utc": "2026-07-16T01:42:57+00:00",
      "tool_calls": [],
      "tool_calls_parse_error": null,
      "tool_calls_parse_ok": false,
      "usage_completion_tokens": 93
    },
    {
      "content_length": 138,
      "content_preview": "2416 ends in 6, and any integer ending in an even digit is divisible by 2. Specifically, 2416 \u00f7 2 = 1208 with no remainder, so it is even.",
      "elapsed_secs": 0.8333439549896866,
      "error_body": null,
      "error_message": null,
      "error_type": null,
      "finish_reason": "stop",
      "first_answer_chunk_index": 0,
      "first_content_chunk_index": 0,
      "first_content_secs": 0.8331313810776919,
      "first_reasoning_chunk_index": 0,
      "first_reasoning_secs": 0.8331302290316671,
      "first_tool_call_chunk_index": null,
      "first_tool_call_secs": null,
      "http_status": 200,
      "label": "reasoning_batch_with_tools",
      "reasoning_content_length": 181,
      "reasoning_content_present": true,
      "reasoning_delta_count": 1,
      "reasoning_same_delta_as_first_answer": true,
      "reasoning_same_delta_as_first_content": true,
      "reasoning_tokens": 49,
      "request_breaking_400": false,
      "request_kwargs_sent": {
        "max_tokens": 16384,
        "messages": [
          {
            "content": "You are a concise streaming diagnostic.",
            "role": "system"
          },
          {
            "content": "The request contains tools, but do not call one. In two short sentences, explain why 2416 is even.",
            "role": "user"
          }
        ],
        "model": "thinkingmachines/inkling",
        "reasoning_effort": "max",
        "stream": true,
        "stream_options": {
          "include_usage": true
        },
        "temperature": 1.0,
        "tool_choice": "none",
        "tools": [
          {
            "function": {
              "description": "Submit the answer for the controlled Inkling probe.",
              "name": "submit_probe",
              "parameters": {
                "additionalProperties": false,
                "properties": {
                  "answer": {
                    "type": "integer"
                  },
                  "checksum": {
                    "type": "string"
                  }
                },
                "required": [
                  "answer",
                  "checksum"
                ],
                "type": "object"
              }
            },
            "type": "function"
          }
        ]
      },
      "response_headers": {},
      "sample": 3,
      "started_utc": "2026-07-16T01:42:58+00:00",
      "tool_calls": [],
      "tool_calls_parse_error": null,
      "tool_calls_parse_ok": false,
      "usage_completion_tokens": 99
    },
    {
      "content_length": 107,
      "content_preview": "2416 ends in 6, an even digit, so it\u2019s divisible by 2. Specifically, 2416 = 2 \u00d7 1208, leaving no remainder.",
      "elapsed_secs": 1.0155134000815451,
      "error_body": null,
      "error_message": null,
      "error_type": null,
      "finish_reason": "stop",
      "first_answer_chunk_index": 0,
      "first_content_chunk_index": 0,
      "first_content_secs": 1.0153173280414194,
      "first_reasoning_chunk_index": 0,
      "first_reasoning_secs": 1.015316325938329,
      "first_tool_call_chunk_index": null,
      "first_tool_call_secs": null,
      "http_status": 200,
      "label": "reasoning_batch_with_tools",
      "reasoning_content_length": 294,
      "reasoning_content_present": true,
      "reasoning_delta_count": 1,
      "reasoning_same_delta_as_first_answer": true,
      "reasoning_same_delta_as_first_content": true,
      "reasoning_tokens": 83,
      "request_breaking_400": false,
      "request_kwargs_sent": {
        "max_tokens": 16384,
        "messages": [
          {
            "content": "You are a concise streaming diagnostic.",
            "role": "system"
          },
          {
            "content": "The request contains tools, but do not call one. In two short sentences, explain why 2416 is even.",
            "role": "user"
          }
        ],
        "model": "thinkingmachines/inkling",
        "reasoning_effort": "max",
        "stream": true,
        "stream_options": {
          "include_usage": true
        },
        "temperature": 1.0,
        "tool_choice": "none",
        "tools": [
          {
            "function": {
              "description": "Submit the answer for the controlled Inkling probe.",
              "name": "submit_probe",
              "parameters": {
                "additionalProperties": false,
                "properties": {
                  "answer": {
                    "type": "integer"
                  },
                  "checksum": {
                    "type": "string"
                  }
                },
                "required": [
                  "answer",
                  "checksum"
                ],
                "type": "object"
              }
            },
            "type": "function"
          }
        ]
      },
      "response_headers": {},
      "sample": 4,
      "started_utc": "2026-07-16T01:42:58+00:00",
      "tool_calls": [],
      "tool_calls_parse_error": null,
      "tool_calls_parse_ok": false,
      "usage_completion_tokens": 126
    },
    {
      "content_length": 150,
      "content_preview": "2416 ends in 6, which is divisible by 2, so the whole number is divisible by 2. Specifically, 2416 \u00f7 2 = 1208 with no remainder, confirming it\u2019s even.",
      "elapsed_secs": 0.8680968971457332,
      "error_body": null,
      "error_message": null,
      "error_type": null,
      "finish_reason": "stop",
      "first_answer_chunk_index": 0,
      "first_content_chunk_index": 0,
      "first_content_secs": 0.8679258620832115,
      "first_reasoning_chunk_index": 0,
      "first_reasoning_secs": 0.8679247600957751,
      "first_tool_call_chunk_index": null,
      "first_tool_call_secs": null,
      "http_status": 200,
      "label": "reasoning_batch_with_tools",
      "reasoning_content_length": 180,
      "reasoning_content_present": true,
      "reasoning_delta_count": 1,
      "reasoning_same_delta_as_first_answer": true,
      "reasoning_same_delta_as_first_content": true,
      "reasoning_tokens": 50,
      "request_breaking_400": false,
      "request_kwargs_sent": {
        "max_tokens": 16384,
        "messages": [
          {
            "content": "You are a concise streaming diagnostic.",
            "role": "system"
          },
          {
            "content": "The request contains tools, but do not call one. In two short sentences, explain why 2416 is even.",
            "role": "user"
          }
        ],
        "model": "thinkingmachines/inkling",
        "reasoning_effort": "max",
        "stream": true,
        "stream_options": {
          "include_usage": true
        },
        "temperature": 1.0,
        "tool_choice": "none",
        "tools": [
          {
            "function": {
              "description": "Submit the answer for the controlled Inkling probe.",
              "name": "submit_probe",
              "parameters": {
                "additionalProperties": false,
                "properties": {
                  "answer": {
                    "type": "integer"
                  },
                  "checksum": {
                    "type": "string"
                  }
                },
                "required": [
                  "answer",
                  "checksum"
                ],
                "type": "object"
              }
            },
            "type": "function"
          }
        ]
      },
      "response_headers": {},
      "sample": 5,
      "started_utc": "2026-07-16T01:42:59+00:00",
      "tool_calls": [],
      "tool_calls_parse_error": null,
      "tool_calls_parse_ok": false,
      "usage_completion_tokens": 103
    }
  ],
  "tool_parse": [
    {
      "content_length": 0,
      "content_preview": "",
      "elapsed_secs": 1.6123002720996737,
      "error_body": null,
      "error_message": null,
      "error_type": null,
      "finish_reason": "tool_calls",
      "first_answer_chunk_index": 0,
      "first_content_chunk_index": null,
      "first_content_secs": null,
      "first_reasoning_chunk_index": 0,
      "first_reasoning_secs": 1.6120970060583204,
      "first_tool_call_chunk_index": 0,
      "first_tool_call_secs": 1.612098990008235,
      "http_status": 200,
      "label": "stream_tool_parse",
      "reasoning_content_length": 212,
      "reasoning_content_present": true,
      "reasoning_delta_count": 1,
      "reasoning_same_delta_as_first_answer": true,
      "reasoning_same_delta_as_first_content": null,
      "reasoning_tokens": 92,
      "request_breaking_400": false,
      "request_kwargs_sent": {
        "max_tokens": 16384,
        "messages": [
          {
            "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
            "role": "system"
          },
          {
            "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
            "role": "user"
          }
        ],
        "model": "thinkingmachines/inkling",
        "reasoning_effort": "max",
        "stream": true,
        "stream_options": {
          "include_usage": true
        },
        "temperature": 1.0,
        "tool_choice": {
          "function": {
            "name": "submit_probe"
          },
          "type": "function"
        },
        "tools": [
          {
            "function": {
              "description": "Submit the answer for the controlled Inkling probe.",
              "name": "submit_probe",
              "parameters": {
                "additionalProperties": false,
                "properties": {
                  "answer": {
                    "type": "integer"
                  },
                  "checksum": {
                    "type": "string"
                  }
                },
                "required": [
                  "answer",
                  "checksum"
                ],
                "type": "object"
              }
            },
            "type": "function"
          }
        ]
      },
      "response_headers": {},
      "sample": 1,
      "started_utc": "2026-07-16T01:42:49+00:00",
      "tool_calls": [
        {
          "arguments_json_error": null,
          "arguments_json_valid": true,
          "arguments_length": 53,
          "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
          "id": "chatcmpl-tool-d7dffbcb467a48e8a7bd7fd01731944d",
          "index": 0,
          "name": "submit_probe",
          "type": "function"
        }
      ],
      "tool_calls_parse_error": null,
      "tool_calls_parse_ok": true,
      "usage_completion_tokens": 122
    },
    {
      "content_length": 0,
      "content_preview": "",
      "elapsed_secs": 1.604369678068906,
      "error_body": null,
      "error_message": null,
      "error_type": null,
      "finish_reason": "tool_calls",
      "first_answer_chunk_index": 0,
      "first_content_chunk_index": null,
      "first_content_secs": null,
      "first_reasoning_chunk_index": 0,
      "first_reasoning_secs": 1.6041622338816524,
      "first_tool_call_chunk_index": 0,
      "first_tool_call_secs": 1.6041636168956757,
      "http_status": 200,
      "label": "stream_tool_parse",
      "reasoning_content_length": 384,
      "reasoning_content_present": true,
      "reasoning_delta_count": 1,
      "reasoning_same_delta_as_first_answer": true,
      "reasoning_same_delta_as_first_content": null,
      "reasoning_tokens": 171,
      "request_breaking_400": false,
      "request_kwargs_sent": {
        "max_tokens": 16384,
        "messages": [
          {
            "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
            "role": "system"
          },
          {
            "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
            "role": "user"
          }
        ],
        "model": "thinkingmachines/inkling",
        "reasoning_effort": "max",
        "stream": true,
        "stream_options": {
          "include_usage": true
        },
        "temperature": 1.0,
        "tool_choice": {
          "function": {
            "name": "submit_probe"
          },
          "type": "function"
        },
        "tools": [
          {
            "function": {
              "description": "Submit the answer for the controlled Inkling probe.",
              "name": "submit_probe",
              "parameters": {
                "additionalProperties": false,
                "properties": {
                  "answer": {
                    "type": "integer"
                  },
                  "checksum": {
                    "type": "string"
                  }
                },
                "required": [
                  "answer",
                  "checksum"
                ],
                "type": "object"
              }
            },
            "type": "function"
          }
        ]
      },
      "response_headers": {},
      "sample": 2,
      "started_utc": "2026-07-16T01:42:51+00:00",
      "tool_calls": [
        {
          "arguments_json_error": null,
          "arguments_json_valid": true,
          "arguments_length": 53,
          "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
          "id": "chatcmpl-tool-5da045b00aac4f21acf9cdb2c22e98bf",
          "index": 0,
          "name": "submit_probe",
          "type": "function"
        }
      ],
      "tool_calls_parse_error": null,
      "tool_calls_parse_ok": true,
      "usage_completion_tokens": 201
    },
    {
      "content_length": 0,
      "content_preview": "",
      "elapsed_secs": 0.9741455230396241,
      "error_body": null,
      "error_message": null,
      "error_type": null,
      "finish_reason": "tool_calls",
      "first_answer_chunk_index": 0,
      "first_content_chunk_index": null,
      "first_content_secs": null,
      "first_reasoning_chunk_index": 0,
      "first_reasoning_secs": 0.973968236008659,
      "first_tool_call_chunk_index": 0,
      "first_tool_call_secs": 0.9739697189070284,
      "http_status": 200,
      "label": "stream_tool_parse",
      "reasoning_content_length": 208,
      "reasoning_content_present": true,
      "reasoning_delta_count": 1,
      "reasoning_same_delta_as_first_answer": true,
      "reasoning_same_delta_as_first_content": null,
      "reasoning_tokens": 82,
      "request_breaking_400": false,
      "request_kwargs_sent": {
        "max_tokens": 16384,
        "messages": [
          {
            "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
            "role": "system"
          },
          {
            "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
            "role": "user"
          }
        ],
        "model": "thinkingmachines/inkling",
        "reasoning_effort": "max",
        "stream": true,
        "stream_options": {
          "include_usage": true
        },
        "temperature": 1.0,
        "tool_choice": {
          "function": {
            "name": "submit_probe"
          },
          "type": "function"
        },
        "tools": [
          {
            "function": {
              "description": "Submit the answer for the controlled Inkling probe.",
              "name": "submit_probe",
              "parameters": {
                "additionalProperties": false,
                "properties": {
                  "answer": {
                    "type": "integer"
                  },
                  "checksum": {
                    "type": "string"
                  }
                },
                "required": [
                  "answer",
                  "checksum"
                ],
                "type": "object"
              }
            },
            "type": "function"
          }
        ]
      },
      "response_headers": {},
      "sample": 3,
      "started_utc": "2026-07-16T01:42:53+00:00",
      "tool_calls": [
        {
          "arguments_json_error": null,
          "arguments_json_valid": true,
          "arguments_length": 53,
          "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
          "id": "chatcmpl-tool-97153bc89070423fb97f8485fba17b19",
          "index": 0,
          "name": "submit_probe",
          "type": "function"
        }
      ],
      "tool_calls_parse_error": null,
      "tool_calls_parse_ok": true,
      "usage_completion_tokens": 112
    },
    {
      "content_length": 0,
      "content_preview": "",
      "elapsed_secs": 0.9422983410768211,
      "error_body": null,
      "error_message": null,
      "error_type": null,
      "finish_reason": "tool_calls",
      "first_answer_chunk_index": 0,
      "first_content_chunk_index": null,
      "first_content_secs": null,
      "first_reasoning_chunk_index": 0,
      "first_reasoning_secs": 0.9421234880574048,
      "first_tool_call_chunk_index": 0,
      "first_tool_call_secs": 0.9421245499979705,
      "http_status": 200,
      "label": "stream_tool_parse",
      "reasoning_content_length": 184,
      "reasoning_content_present": true,
      "reasoning_delta_count": 1,
      "reasoning_same_delta_as_first_answer": true,
      "reasoning_same_delta_as_first_content": null,
      "reasoning_tokens": 79,
      "request_breaking_400": false,
      "request_kwargs_sent": {
        "max_tokens": 16384,
        "messages": [
          {
            "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
            "role": "system"
          },
          {
            "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
            "role": "user"
          }
        ],
        "model": "thinkingmachines/inkling",
        "reasoning_effort": "max",
        "stream": true,
        "stream_options": {
          "include_usage": true
        },
        "temperature": 1.0,
        "tool_choice": {
          "function": {
            "name": "submit_probe"
          },
          "type": "function"
        },
        "tools": [
          {
            "function": {
              "description": "Submit the answer for the controlled Inkling probe.",
              "name": "submit_probe",
              "parameters": {
                "additionalProperties": false,
                "properties": {
                  "answer": {
                    "type": "integer"
                  },
                  "checksum": {
                    "type": "string"
                  }
                },
                "required": [
                  "answer",
                  "checksum"
                ],
                "type": "object"
              }
            },
            "type": "function"
          }
        ]
      },
      "response_headers": {},
      "sample": 4,
      "started_utc": "2026-07-16T01:42:54+00:00",
      "tool_calls": [
        {
          "arguments_json_error": null,
          "arguments_json_valid": true,
          "arguments_length": 53,
          "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
          "id": "chatcmpl-tool-9697f7ba0ba049a9b54d688d557cb6a8",
          "index": 0,
          "name": "submit_probe",
          "type": "function"
        }
      ],
      "tool_calls_parse_error": null,
      "tool_calls_parse_ok": true,
      "usage_completion_tokens": 109
    },
    {
      "content_length": 0,
      "content_preview": "",
      "elapsed_secs": 1.3673416171222925,
      "error_body": null,
      "error_message": null,
      "error_type": null,
      "finish_reason": "tool_calls",
      "first_answer_chunk_index": 0,
      "first_content_chunk_index": null,
      "first_content_secs": null,
      "first_reasoning_chunk_index": 0,
      "first_reasoning_secs": 1.3671280411072075,
      "first_tool_call_chunk_index": 0,
      "first_tool_call_secs": 1.367129524005577,
      "http_status": 200,
      "label": "stream_tool_parse",
      "reasoning_content_length": 306,
      "reasoning_content_present": true,
      "reasoning_delta_count": 1,
      "reasoning_same_delta_as_first_answer": true,
      "reasoning_same_delta_as_first_content": null,
      "reasoning_tokens": 138,
      "request_breaking_400": false,
      "request_kwargs_sent": {
        "max_tokens": 16384,
        "messages": [
          {
            "content": "You are a deterministic tool-use diagnostic. Solve the arithmetic carefully, then call submit_probe exactly once.",
            "role": "system"
          },
          {
            "content": "Compute (37 * 41) + (29 * 31). Call submit_probe with the integer answer and checksum exactly 'inkling-controlled-v1'.",
            "role": "user"
          }
        ],
        "model": "thinkingmachines/inkling",
        "reasoning_effort": "max",
        "stream": true,
        "stream_options": {
          "include_usage": true
        },
        "temperature": 1.0,
        "tool_choice": {
          "function": {
            "name": "submit_probe"
          },
          "type": "function"
        },
        "tools": [
          {
            "function": {
              "description": "Submit the answer for the controlled Inkling probe.",
              "name": "submit_probe",
              "parameters": {
                "additionalProperties": false,
                "properties": {
                  "answer": {
                    "type": "integer"
                  },
                  "checksum": {
                    "type": "string"
                  }
                },
                "required": [
                  "answer",
                  "checksum"
                ],
                "type": "object"
              }
            },
            "type": "function"
          }
        ]
      },
      "response_headers": {},
      "sample": 5,
      "started_utc": "2026-07-16T01:42:55+00:00",
      "tool_calls": [
        {
          "arguments_json_error": null,
          "arguments_json_valid": true,
          "arguments_length": 53,
          "arguments_preview": "{\"answer\": 2416, \"checksum\": \"inkling-controlled-v1\"}",
          "id": "chatcmpl-tool-91bff147e35748abb77a76ccc38c7014",
          "index": 0,
          "name": "submit_probe",
          "type": "function"
        }
      ],
      "tool_calls_parse_error": null,
      "tool_calls_parse_ok": true,
      "usage_completion_tokens": 168
    }
  ],
  "truncation": [
    {
      "content_length": 0,
      "content_preview": "",
      "elapsed_secs": 56.964475540909916,
      "error_body": {
        "code": 400,
        "message": "Tool calls cutoff by max_tokens.",
        "type": "Bad Request"
      },
      "error_message": "Error code: 400 - {'error': {'code': 400, 'message': 'Tool calls cutoff by max_tokens.', 'type': 'Bad Request'}}",
      "error_type": "BadRequestError",
      "explicit_max_tokens_cutoff": true,
      "finish_reason": null,
      "first_answer_chunk_index": null,
      "first_content_chunk_index": null,
      "first_content_secs": null,
      "first_reasoning_chunk_index": null,
      "first_reasoning_secs": null,
      "first_tool_call_chunk_index": null,
      "first_tool_call_secs": null,
      "http_status": 400,
      "label": "truncation_mt8192",
      "max_tokens_probe": 8192,
      "reasoning_content_length": 0,
      "reasoning_content_present": false,
      "reasoning_delta_count": 0,
      "reasoning_same_delta_as_first_answer": null,
      "reasoning_same_delta_as_first_content": null,
      "reasoning_tokens": null,
      "request_breaking_400": true,
      "request_kwargs_sent": {
        "max_tokens": 8192,
        "messages": [
          {
            "content": "You are a tool-call truncation diagnostic. Follow the requested sequence exactly and do not summarize it.",
            "role": "system"
          },
          {
            "content": "Call submit_sequence once. Its values array must contain every integer from 1 through 5000, in order, with no omissions.",
            "role": "user"
          }
        ],
        "model": "thinkingmachines/inkling",
        "reasoning_effort": "max",
        "stream": true,
        "stream_options": {
          "include_usage": true
        },
        "temperature": 1.0,
        "tool_choice": {
          "function": {
            "name": "submit_sequence"
          },
          "type": "function"
        },
        "tools": [
          {
            "function": {
              "description": "Submit a long integer sequence without omissions.",
              "name": "submit_sequence",
              "parameters": {
                "additionalProperties": false,
                "properties": {
                  "values": {
                    "items": {
                      "type": "integer"
                    },
                    "type": "array"
                  }
                },
                "required": [
                  "values"
                ],
                "type": "object"
              }
            },
            "type": "function"
          }
        ]
      },
      "response_headers": {},
      "sample": 1,
      "sequence_complete": false,
      "sequence_is_exact_prefix": false,
      "sequence_length": null,
      "started_utc": "2026-07-16T01:43:03+00:00",
      "tool_calls": [],
      "tool_calls_parse_error": "expected exactly one tool call, got 0",
      "tool_calls_parse_ok": false,
      "truncation_category": "confirmed_truncation",
      "truncation_category_reason": "request returned an explicit max_tokens cutoff error",
      "usage_completion_tokens": null
    },
    {
      "content_length": 0,
      "content_preview": "",
      "elapsed_secs": 56.85186135908589,
      "error_body": {
        "code": 400,
        "message": "Tool calls cutoff by max_tokens.",
        "type": "Bad Request"
      },
      "error_message": "Error code: 400 - {'error': {'code': 400, 'message': 'Tool calls cutoff by max_tokens.', 'type': 'Bad Request'}}",
      "error_type": "BadRequestError",
      "explicit_max_tokens_cutoff": true,
      "finish_reason": null,
      "first_answer_chunk_index": null,
      "first_content_chunk_index": null,
      "first_content_secs": null,
      "first_reasoning_chunk_index": null,
      "first_reasoning_secs": null,
      "first_tool_call_chunk_index": null,
      "first_tool_call_secs": null,
      "http_status": 400,
      "label": "truncation_mt8192",
      "max_tokens_probe": 8192,
      "reasoning_content_length": 0,
      "reasoning_content_present": false,
      "reasoning_delta_count": 0,
      "reasoning_same_delta_as_first_answer": null,
      "reasoning_same_delta_as_first_content": null,
      "reasoning_tokens": null,
      "request_breaking_400": true,
      "request_kwargs_sent": {
        "max_tokens": 8192,
        "messages": [
          {
            "content": "You are a tool-call truncation diagnostic. Follow the requested sequence exactly and do not summarize it.",
            "role": "system"
          },
          {
            "content": "Call submit_sequence once. Its values array must contain every integer from 1 through 5000, in order, with no omissions.",
            "role": "user"
          }
        ],
        "model": "thinkingmachines/inkling",
        "reasoning_effort": "max",
        "stream": true,
        "stream_options": {
          "include_usage": true
        },
        "temperature": 1.0,
        "tool_choice": {
          "function": {
            "name": "submit_sequence"
          },
          "type": "function"
        },
        "tools": [
          {
            "function": {
              "description": "Submit a long integer sequence without omissions.",
              "name": "submit_sequence",
              "parameters": {
                "additionalProperties": false,
                "properties": {
                  "values": {
                    "items": {
                      "type": "integer"
                    },
                    "type": "array"
                  }
                },
                "required": [
                  "values"
                ],
                "type": "object"
              }
            },
            "type": "function"
          }
        ]
      },
      "response_headers": {},
      "sample": 2,
      "sequence_complete": false,
      "sequence_is_exact_prefix": false,
      "sequence_length": null,
      "started_utc": "2026-07-16T01:44:00+00:00",
      "tool_calls": [],
      "tool_calls_parse_error": "expected exactly one tool call, got 0",
      "tool_calls_parse_ok": false,
      "truncation_category": "confirmed_truncation",
      "truncation_category_reason": "request returned an explicit max_tokens cutoff error",
      "usage_completion_tokens": null
    },
    {
      "content_length": 0,
      "content_preview": "",
      "elapsed_secs": 98.51139260595664,
      "error_body": null,
      "error_message": null,
      "error_type": null,
      "explicit_max_tokens_cutoff": false,
      "finish_reason": "tool_calls",
      "first_answer_chunk_index": 0,
      "first_content_chunk_index": null,
      "first_content_secs": null,
      "first_reasoning_chunk_index": 0,
      "first_reasoning_secs": 98.51118085393682,
      "first_tool_call_chunk_index": 0,
      "first_tool_call_secs": 98.51118202600628,
      "http_status": 200,
      "label": "truncation_mt16384",
      "max_tokens_probe": 16384,
      "reasoning_content_length": 71,
      "reasoning_content_present": true,
      "reasoning_delta_count": 1,
      "reasoning_same_delta_as_first_answer": true,
      "reasoning_same_delta_as_first_content": null,
      "reasoning_tokens": 20,
      "request_breaking_400": false,
      "request_kwargs_sent": {
        "max_tokens": 16384,
        "messages": [
          {
            "content": "You are a tool-call truncation diagnostic. Follow the requested sequence exactly and do not summarize it.",
            "role": "system"
          },
          {
            "content": "Call submit_sequence once. Its values array must contain every integer from 1 through 5000, in order, with no omissions.",
            "role": "user"
          }
        ],
        "model": "thinkingmachines/inkling",
        "reasoning_effort": "max",
        "stream": true,
        "stream_options": {
          "include_usage": true
        },
        "temperature": 1.0,
        "tool_choice": {
          "function": {
            "name": "submit_sequence"
          },
          "type": "function"
        },
        "tools": [
          {
            "function": {
              "description": "Submit a long integer sequence without omissions.",
              "name": "submit_sequence",
              "parameters": {
                "additionalProperties": false,
                "properties": {
                  "values": {
                    "items": {
                      "type": "integer"
                    },
                    "type": "array"
                  }
                },
                "required": [
                  "values"
                ],
                "type": "object"
              }
            },
            "type": "function"
          }
        ]
      },
      "response_headers": {},
      "sample": 1,
      "sequence_complete": true,
      "sequence_is_exact_prefix": true,
      "sequence_length": 5000,
      "started_utc": "2026-07-16T01:44:57+00:00",
      "tool_calls": [
        {
          "arguments_json_error": null,
          "arguments_json_valid": true,
          "arguments_length": 28905,
          "arguments_preview": "{\"values\": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, 146, 147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 173, 174, 175, 176, 177, 178, 179, 180, 181, 182, 183, 184, 185, 186, 187, 188, 189, 190, 191, 192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212, 213, 214, 215, 216, 217, 218, 219, 220, 221, 222, 223, 224, 225, 226, 227, 228, 229, 230, 231, 232, 233, 234, 235, 236, 237, 238, 239, 240, 241, 242, 243, 244, 245, 246, 247, 248, 249, 250, 251, 252, 253, 254, 255, 256, 257, 258, 259, 260, 261, 262, 263, 264, 265, 266, 267, 268, 269, 270, 271, 272, 273, 274, 275, 276, 277, 278, 279, 280, 281, 282, 283, 284, 285, 286, 287, 288, 289, 290, 291, 292, 293, 294, 295, 296, 297, 298, 299, 300, 301, 302, 303, 304, 305, 306, 307, 308, 309, 310, 311, 312, 313, 314, 315, 316, 317, 318, 319, 320, 321, 322, 323, 324, 325, 326, 327, 328, 329, 330, 331, 332, 333, 334, 335, 336, 337, 338, 339, 340, 341, 342, 343, 344, 345, 346, 347, 348, 349, 350, 351, 352, 353, 354, 355, 356, 357, 358, 359, 360, 361, 362, 363, 364, 365, 366, 367, 368, 369, 370, 371, 372, 373, 374, 375, 376, 377, 378, 379, 380, 381, 382, 383, 384, 385, 386, 387, 388, 389, 390, 391, 392, 393, 394, 395, 396, 397, 398, 399, 400, 401, 402, 403, 404, 405, 406, 407, 408, 409, 410, 411, 412, 413, 414, 415, 416, 417, 418, 419, 4... [truncated 26905 chars]",
          "id": "chatcmpl-tool-3d67286998c746e9911501405b42c929",
          "index": 0,
          "name": "submit_sequence",
          "type": "function"
        }
      ],
      "tool_calls_parse_error": null,
      "tool_calls_parse_ok": true,
      "truncation_category": "inconclusive",
      "truncation_category_reason": "the complete requested sequence was returned; no truncation observed",
      "usage_completion_tokens": 14041
    },
    {
      "content_length": 0,
      "content_preview": "",
      "elapsed_secs": 99.10780706699006,
      "error_body": null,
      "error_message": null,
      "error_type": null,
      "explicit_max_tokens_cutoff": false,
      "finish_reason": "tool_calls",
      "first_answer_chunk_index": 0,
      "first_content_chunk_index": null,
      "first_content_secs": null,
      "first_reasoning_chunk_index": 0,
      "first_reasoning_secs": 99.1076179780066,
      "first_tool_call_chunk_index": 0,
      "first_tool_call_secs": 99.10761967091821,
      "http_status": 200,
      "label": "truncation_mt16384",
      "max_tokens_probe": 16384,
      "reasoning_content_length": 162,
      "reasoning_content_present": true,
      "reasoning_delta_count": 1,
      "reasoning_same_delta_as_first_answer": true,
      "reasoning_same_delta_as_first_content": null,
      "reasoning_tokens": 36,
      "request_breaking_400": false,
      "request_kwargs_sent": {
        "max_tokens": 16384,
        "messages": [
          {
            "content": "You are a tool-call truncation diagnostic. Follow the requested sequence exactly and do not summarize it.",
            "role": "system"
          },
          {
            "content": "Call submit_sequence once. Its values array must contain every integer from 1 through 5000, in order, with no omissions.",
            "role": "user"
          }
        ],
        "model": "thinkingmachines/inkling",
        "reasoning_effort": "max",
        "stream": true,
        "stream_options": {
          "include_usage": true
        },
        "temperature": 1.0,
        "tool_choice": {
          "function": {
            "name": "submit_sequence"
          },
          "type": "function"
        },
        "tools": [
          {
            "function": {
              "description": "Submit a long integer sequence without omissions.",
              "name": "submit_sequence",
              "parameters": {
                "additionalProperties": false,
                "properties": {
                  "values": {
                    "items": {
                      "type": "integer"
                    },
                    "type": "array"
                  }
                },
                "required": [
                  "values"
                ],
                "type": "object"
              }
            },
            "type": "function"
          }
        ]
      },
      "response_headers": {},
      "sample": 2,
      "sequence_complete": true,
      "sequence_is_exact_prefix": true,
      "sequence_length": 5000,
      "started_utc": "2026-07-16T01:46:36+00:00",
      "tool_calls": [
        {
          "arguments_json_error": null,
          "arguments_json_valid": true,
          "arguments_length": 28905,
          "arguments_preview": "{\"values\": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, 146, 147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 173, 174, 175, 176, 177, 178, 179, 180, 181, 182, 183, 184, 185, 186, 187, 188, 189, 190, 191, 192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212, 213, 214, 215, 216, 217, 218, 219, 220, 221, 222, 223, 224, 225, 226, 227, 228, 229, 230, 231, 232, 233, 234, 235, 236, 237, 238, 239, 240, 241, 242, 243, 244, 245, 246, 247, 248, 249, 250, 251, 252, 253, 254, 255, 256, 257, 258, 259, 260, 261, 262, 263, 264, 265, 266, 267, 268, 269, 270, 271, 272, 273, 274, 275, 276, 277, 278, 279, 280, 281, 282, 283, 284, 285, 286, 287, 288, 289, 290, 291, 292, 293, 294, 295, 296, 297, 298, 299, 300, 301, 302, 303, 304, 305, 306, 307, 308, 309, 310, 311, 312, 313, 314, 315, 316, 317, 318, 319, 320, 321, 322, 323, 324, 325, 326, 327, 328, 329, 330, 331, 332, 333, 334, 335, 336, 337, 338, 339, 340, 341, 342, 343, 344, 345, 346, 347, 348, 349, 350, 351, 352, 353, 354, 355, 356, 357, 358, 359, 360, 361, 362, 363, 364, 365, 366, 367, 368, 369, 370, 371, 372, 373, 374, 375, 376, 377, 378, 379, 380, 381, 382, 383, 384, 385, 386, 387, 388, 389, 390, 391, 392, 393, 394, 395, 396, 397, 398, 399, 400, 401, 402, 403, 404, 405, 406, 407, 408, 409, 410, 411, 412, 413, 414, 415, 416, 417, 418, 419, 4... [truncated 26905 chars]",
          "id": "chatcmpl-tool-5c9123c83f2d4377a897940814dedcc9",
          "index": 0,
          "name": "submit_sequence",
          "type": "function"
        }
      ],
      "tool_calls_parse_error": null,
      "tool_calls_parse_ok": true,
      "truncation_category": "inconclusive",
      "truncation_category_reason": "the complete requested sequence was returned; no truncation observed",
      "usage_completion_tokens": 14057
    }
  ]
}
```
<!-- inkling-probe:follow-ups:end -->
