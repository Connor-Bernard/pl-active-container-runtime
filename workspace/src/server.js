const express = require('express');
const express_ws = require('express-ws');
const pty = require('node-pty');
const path = require('path');
const cl_args = require('command-line-args');
const cl_usage = require('command-line-usage');

const app = express();
express_ws(app);

const argument_option_defs = [
  {
    name: 'help',
    alias: 'h',
    type: Boolean,
    description: 'display this usage guide',
  },
  {
    name: 'port',
    alias: 'p',
    type: Number,
    defaultValue: 8080,
    description: 'port that the server is run on (default 8080)',
  },
  {
    name: 'working-dir',
    alias: 'w',
    type: String,
    defaultValue: process.env.HOME,
    description: 'initial working directory (default $HOME)',
  },
];
const options = cl_args(argument_option_defs);
if (options.help) {
  const usage = cl_usage([{ header: 'Arguments', optionList: argument_option_defs }]);
  console.log(usage);
  return;
}

const default_env = {
  LC_CTYPE: 'C.UTF-8',
};

function cleanOutput(output) {
  return output.replace(/\x1B\[[0-9;]*[JKmsu]/g, "").replace(/[\x00-\x1F\x7F-\x9F]/g, "");
}

const missions = [
  { 
    instruction: "Start your program so that it's at the first line in main, using one command.",
    description: "Start your program so that it's at the first line in main, using one command.",
    check: (output) => {
      const cleanedOutput = cleanOutput(output);
      return /main\s*\(\)\s*at\s*test_pwd_checker\.c:6/.test(cleanedOutput) &&
             /printf\("Running tests...\s*\\n\\n"\);/.test(cleanedOutput);
    }
  },
  { 
    instruction: "Step over the printf line in the program.",
    description: "The first line in main is a call to printf. We do not want to step into this function. Step over this line in the program.",
    check: (output) => {
      const cleanedOutput = cleanOutput(output);
      return /const char \*test1_first = "Abraham";/.test(cleanedOutput);
    }
  },
  { 
    instruction: "Step until the program is on the check_password call.",
    description: "Step until the program is on the check_password call. Note that the line with an arrow next to it is the line we're currently on, but has not been executed yet.",
    check: (output) => {
      const cleanedOutput = cleanOutput(output);
      return /bool test1 = check_password\(test1_first, test1_last, test1_pwd\);/.test(cleanedOutput);
    }
  },
  { 
    instruction: "Step into check_password.",
    description: "Step into check_password.",
    check: (output) => {
      const cleanedOutput = cleanOutput(output);
      return /check_password \(first_name=/.test(cleanedOutput) &&
             /lower = check_lower\(password\);/.test(cleanedOutput);
    }
  },
  { 
    instruction: "Step into check_lower.",
    description: "Step into check_lower.",
    check: (output) => {
      const cleanedOutput = cleanOutput(output);
      return /check_lower \(password=/.test(cleanedOutput) &&
             /while \(\*password != '\\0'\) {/.test(cleanedOutput);
    }
  },
  { 
    instruction: "Print the value of password (password is a string).",
    description: "Print the value of password (password is a string).",
    check: (output) => {
      const cleanedOutput = cleanOutput(output);
      return /\$\d+\s*=\s*0x[0-9a-f]+\s*"qrtv\?,mp!ltrA0b13rab4ham"/.test(cleanedOutput);
    }
  },
  { 
    instruction: "Step out of check_lower immediately.",
    description: "Step out of check_lower immediately. Do not step until the function returns.",
    check: (output) => {
      const cleanedOutput = cleanOutput(output);
      return /Run till exit from #0\s*check_lower/.test(cleanedOutput) &&
             /Value returned is \$\d+\s*=\s*true/.test(cleanedOutput);
    }
  },
  { 
    instruction: "Step into check_length.",
    description: "Step into check_length.",
    check: (output) => {
      const cleanedOutput = cleanOutput(output);
      return /check_length \(password=/.test(cleanedOutput) &&
             /int length = strlen\(password\);/.test(cleanedOutput);
    }
  },
  { 
    instruction: "Step to the last line of the function.",
    description: "Step to the last line of the function.",
    check: (output) => {
      const cleanedOutput = cleanOutput(output);
      return /return meets_len_req;/.test(cleanedOutput);
    }
  },
  { 
    instruction: "Print the return value of the function.",
    description: "Print the return value of the function. The return value should be false.",
    check: (output) => {
      const cleanedOutput = cleanOutput(output);
      return /\$\d+\s*=\s*true/.test(cleanedOutput);
    }
  },
  { 
    instruction: "Print the value of length.",
    description: "Print the value of length. It looks like length was correct, so there must be some logic issue on line 24.",
    check: (output) => {
      const cleanedOutput = cleanOutput(output);
      return /\$\d+\s*=\s*24/.test(cleanedOutput);
    }
  },
  { 
    instruction: "Quit GDB.",
    description: "Quit GDB. GDB might ask you if you want to quit, type 'y' (but do not add 'y' to ex2_commands.txt).",
    check: (output) => {
      const cleanedOutput = cleanOutput(output);
      return /Quit anyway\? \(y or n\)/.test(cleanedOutput);
    }
  }
];

let currentMission = 0;

// Static files
app.get('/', (req, res) => res.sendFile(path.join(__dirname, 'index.html')));
app.use('/xterm', express.static('node_modules/xterm'));
app.use('/xterm-fit', express.static('node_modules/xterm-addon-fit'));

// Create one pseudoterminal that all connections share
let websockets = {};
let ws_id = 0;
let term_output = '';
let term;

const spawn_terminal = () => {
  term_output = '';
  term = pty.spawn('gdb', [], {
    name: 'xterm-color',
    cols: 80,
    rows: 24,
    cwd: options['working-dir'],
    env: Object.assign({}, default_env, process.env),
  });
  
  term.write('file ./pwd_checker\n');

  term.on('data', function (data) {
    term_output += data;
    Object.values(websockets).forEach((ws) => {
      if (ws.readyState === 1) {
        ws.send(JSON.stringify({ type: 'output', data: data }));
        ws.send(JSON.stringify({ type: 'banner', data: term_output }));
      }
    });
    
    if (currentMission < missions.length && missions[currentMission].check(term_output)) {
      currentMission++;
      Object.values(websockets).forEach((ws) => {
        if (ws.readyState === 1) {
          ws.send(JSON.stringify({
            type: 'mission_complete',
            currentMission: currentMission,
            instruction: currentMission < missions.length ? missions[currentMission].instruction : 'All missions completed!',
            description: currentMission < missions.length ? missions[currentMission].description : 'Congratulations! You have completed all missions.'
          }));
        }
      });
      term_output = '';
    }
  });
  term.on('exit', () => {
    Object.values(websockets).forEach((ws) => {
      if (ws.readyState === 1) {
        ws.send(JSON.stringify({ type: 'output', data: '[Process completed]\r\n\r\n' }));
      }
    });
    spawn_terminal();
  });
};
spawn_terminal();

app.ws('/', (ws, req) => {
  const id = ws_id++;
  websockets[id] = ws;
  ws.send(JSON.stringify({
    type: 'init',
    currentMission: currentMission,
    instruction: missions[currentMission].instruction,
    description: missions[currentMission].description
  }));

  ws.on('message', (msg) => {
    const val = JSON.parse(msg);
    if (val.event === 'data') {
      term.write(val.value);
    } else if (val.event === 'resize') {
      term.resize(val.value.cols, val.value.rows);
    } else if (val.event === 'heartbeat') {
      // do nothing
    }
  });
  ws.on('close', (msg) => {
    delete websockets[id];
  });
});

app.listen(options.port, () =>
  console.log(`XTerm server listening at http://localhost:${options.port}`),
);