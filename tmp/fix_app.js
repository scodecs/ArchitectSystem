const fs = require('fs');
const path = 'e:\\Code\\ArchitectSystem\\frontend\\src\\App.jsx';
let content = fs.readFileSync(path, 'utf8');

const oldBlock = /setIsCalculating\(true\);\s+try\s+\{\s+await fetch\(`\$\{API_BASE_URL\}\/api\/project\/\$\{projectId\}\/evaluate`,\s+\{\s+method:\s+'POST'\s+\}\);\s+\}\s+catch/m;

const newBlock = `setIsCalculating(true);
          try {
              await fetch(\`\${API_BASE_URL}/api/project/\${projectId}/evaluate\`, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({
                      provider: providerId,
                      model_id: modelId
                  })
              });
          } catch`;

if (oldBlock.test(content)) {
    console.log("Found target block. Replacing...");
    content = content.replace(oldBlock, newBlock);
    fs.writeFileSync(path, content);
    console.log("Replacement successful.");
} else {
    console.log("Target block NOT found.");
    // Log a bit of content to see why
    const match = content.match(/setIsCalculating\(true\)/);
    if (match) {
        console.log("Found setIsCalculating(true), showing context:");
        console.log(content.substring(match.index, match.index + 200));
    }
}
