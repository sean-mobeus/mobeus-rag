<!DOCTYPE html>
<html>
<head>
  <title>Mobeus Debug Log</title>
  <style>
    body { font-family: sans-serif; padding: 2rem; background: #f9f9f9; }
    pre { background: #eee; padding: 1rem; border-radius: 6px; overflow-x: auto; }
    h2 { border-bottom: 1px solid #ccc; margin-top: 2rem; }
  </style>
</head>
<body>
  <h1>Mobeus Assistant — Debug Log</h1>
  <?php
    $lines = file("debug_log.jsonl") or die("No log file found.");
    $lines = array_reverse($lines); // show newest first
    foreach ($lines as $line) {
      $entry = json_decode($line, true);
      echo "<h2>{$entry['timestamp']}</h2>";
      echo "<strong>Query:</strong> {$entry['query']}<br><br>";
      echo "<strong>Answer:</strong><br><pre>{$entry['answer']}</pre>";
      echo "<strong>Top Chunks:</strong><br>";
      echo "<pre>" . json_encode($entry['top_chunks'], JSON_PRETTY_PRINT) . "</pre>";
    }
  ?>
</body>
</html>