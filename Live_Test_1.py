# Aktiviere das venv und starte Python
  source .venv/Scripts/activate
  python

  # Test-Code:
  from pathlib import Path
  import sys
  sys.path.insert(0, str(Path.cwd() / "src"))

  from local_insight_engine.persistence.repository import SessionRepository
  from local_insight_engine.models.analysis import AnalysisResult, Insight
  from uuid import uuid4

  # Repository erstellen
  repo = SessionRepository()

  # Test-Dokument (nimm eine echte PDF/TXT Datei)
  test_doc = Path("german_sample.txt")  # oder eine andere Datei die du hast

  # Test-Analysis Result
  analysis = AnalysisResult(
      source_processed_text_id=uuid4(),
      insights=[
          Insight(
              title="Test Insight",
              content="This is a test insight about the document",
              confidence=0.9,
              category="test"
          )
      ],
      executive_summary="Test document analysis"
  )

  # Session erstellen
  session = repo.create_session(
      document_path=test_doc,
      analysis_result=analysis,
      display_name="Live Test Document",
      tags=["test", "live", "demo"]
  )

  print(f"Session created: {session.session_id}")
  print(f"Document: {session.document_display_name}")
  print(f"Tags: {session.session_tags}")