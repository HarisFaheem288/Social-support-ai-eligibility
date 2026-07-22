"""
Observability layer (Langfuse integration).

Uses real Langfuse if LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY are set as
environment variables (see .env.example). If not configured — which is the
default for local/offline development — traces are written to a local
JSONL file instead, so every agent step is still observable and auditable
without requiring a Langfuse cloud account or self-hosted server.
"""
import os
import json
import time
from datetime import datetime
from contextlib import contextmanager

LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
LOCAL_TRACE_LOG = os.getenv("LOCAL_TRACE_LOG", "logs/agent_traces.jsonl")

_langfuse_client = None
_use_real_langfuse = False

if LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY:
    try:
        from langfuse import Langfuse
        _langfuse_client = Langfuse(public_key=LANGFUSE_PUBLIC_KEY, secret_key=LANGFUSE_SECRET_KEY)
        _use_real_langfuse = True
    except Exception as e:
        print(f"[tracing] Langfuse credentials found but client init failed, falling back to local log: {e}")


def _write_local_trace(record: dict):
    os.makedirs(os.path.dirname(LOCAL_TRACE_LOG), exist_ok=True)
    with open(LOCAL_TRACE_LOG, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")


@contextmanager
def trace_step(trace_name: str, step_name: str, input_summary: dict):
    """
    Wraps a single agent node execution and records:
    - step name, start/end time, duration
    - a summary of inputs (not the full raw documents, to keep traces small)
    - the output the node produced (set via the yielded dict's 'output' key)
    - any exception raised

    Usage:
        with trace_step("applicant_assessment", "extraction", {"doc_folder": path}) as t:
            ... do work ...
            t["output"] = {"applicant_id": 1}
    """
    start = time.time()
    result_holder = {"output": None, "error": None}
    try:
        yield result_holder
    except Exception as e:
        result_holder["error"] = str(e)
        raise
    finally:
        duration = time.time() - start
        record = {
            "trace_name": trace_name,
            "step_name": step_name,
            "timestamp": datetime.utcnow().isoformat(),
            "duration_seconds": round(duration, 3),
            "input_summary": input_summary,
            "output_summary": result_holder["output"],
            "error": result_holder["error"],
        }

        if _use_real_langfuse:
            try:
                span = _langfuse_client.span(
                    name=step_name,
                    input=input_summary,
                    output=result_holder["output"],
                )
                span.end()
            except Exception as e:
                print(f"[tracing] Langfuse span failed, falling back to local log: {e}")
                _write_local_trace(record)
        else:
            _write_local_trace(record)

        print(f"[tracing] {step_name} completed in {duration:.2f}s"
              f"{' (ERROR: ' + result_holder['error'] + ')' if result_holder['error'] else ''}")
