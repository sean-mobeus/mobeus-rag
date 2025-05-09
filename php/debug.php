<head>
  <title>Mobeus Assistant — Debug Log</title>
  <style>
    body {
      font-family: sans-serif;
      padding: 2rem;
      background: #f9f9f9;
    }
    h1 {
      margin-bottom: 1rem;
    }
    pre {
      background: #eee;
      padding: 1rem;
      border-radius: 6px;
      white-space: pre-wrap;
      word-break: break-word;
      overflow-x: auto;
      max-width: 100%;
      display: block;
    }
    details {
      border: 1px solid #ccc;
      border-radius: 8px;
      padding: 1rem;
      background: #fff;
    }
    details summary {
      font-weight: bold;
      font-size: 1rem;
      cursor: pointer;
      margin-bottom: 0.5rem;
    }
    details[open] summary::after {
      content: " ▲";
    }
    details summary::after {
      content: " ▼";
    }
  </style>
</head>
<body>
  <h1>Mobeus Assistant — Debug Log</h1>

  <?php
  echo "<p style='color: red; font-weight: bold;'>🔥 I AM THE LATEST DEBUG.PHP 🔥</p>";
  echo "<p><strong>debug.php loaded from:</strong> " . __FILE__ . "</p>";

  // $env = parse_ini_file(__DIR__ . '/../.env');
  // if (isset($env['MOBEUS_DEBUG_LOG'])) {
  //   putenv("MOBEUS_DEBUG_LOG=" . $env['MOBEUS_DEBUG_LOG']);
  // }

  $log_file = realpath(__DIR__ . '/../rag_debug.jsonl');
  echo "<p><strong>Reading from:</strong> $log_file</p>";

  $lines = file($log_file) or die("<h2>No log file found.</h2>");
  $lines = array_reverse($lines); // newest first

  foreach ($lines as $line) {
    $entry = json_decode($line, true);
    if (!$entry || !isset($entry['timestamp'])) continue;

    $timestamp = $entry['timestamp'] ?? '';
    $query = $entry['query'] ?? '';
    $answer = $entry['answer'] ?? '';
    $timings = $entry['timings'] ?? [];
    $chunks = $entry['top_chunks'] ?? [];

    echo "<details style='margin-bottom: 2rem;'>";
    echo "<summary><strong>$timestamp</strong> — <em>$query</em></summary>";
    echo "<div style='margin-top: 1rem;'>";

    echo "<strong>Answer:</strong><br><pre>$answer</pre>";

    echo "<strong>Timings (sec):</strong><br>";
    if (!empty($timings)) {
      $gpt_time = $timings['gpt'] ?? 0;
      $timing_style = ($gpt_time > 5.0) ? "color: red;" : "color: green;";
      echo "<pre style='$timing_style'>" . json_encode($timings, JSON_PRETTY_PRINT) . "</pre>";
    } else {
      echo "<pre><em>No timing data available</em></pre>";
    }

    echo "<strong>Top Chunks:</strong><br>";
    echo "<pre>" . json_encode($chunks, JSON_PRETTY_PRINT) . "</pre>";

    echo "<details><summary style='margin-top: 1rem;'>🔍 RAW JSON</summary>";
    echo "<pre>" . htmlentities($line) . "</pre></details>";

    echo "</div></details>";
  }
  ?>
</body>