(function (w) {
  const mqtt_user = "mqtt_user";
  let mqtt_passwd = "";
  const deviceId = "raspberrypi";
  const mqttUrl = "ws://95.216.146.106:8084/mqtt";

  const term = new Terminal({
    cursorBlink: true,
    macOptionIsMeta: true,
    scrollback: true,
  });
  term.attachCustomKeyEventHandler(customKeyEventHandler);
  const fit = new FitAddon.FitAddon();
  term.loadAddon(fit);
  term.loadAddon(new WebLinksAddon.WebLinksAddon());
  term.loadAddon(new SearchAddon.SearchAddon());

  term.open(document.getElementById("terminal"));
  fit.fit();
  term.resize(15, 50);
  console.log(`size: ${term.cols} columns, ${term.rows} rows`);
  fit.fit();

  term.writeln("You can copy with ctrl+shift+x");
  term.writeln("You can paste with ctrl+shift+v");

  term.writeln("Please enter your MQTT password:");
  let inputBuffer = "";
  term.onData((data) => {
    if (data.charCodeAt(0) === 13) {
      mqtt_passwd = inputBuffer;
      console.log("mqtt password:", mqtt_passwd);
      term.clear();
      term.writeln("Connecting to MQTT...");
      term.writeln("You can copy with ctrl+shift+x");
      term.writeln("You can paste with ctrl+shift+v");
      inputBuffer = "";
    } else if (data.charCodeAt(0) === 127) {
      inputBuffer = inputBuffer.slice(0, -1);
      term.write("\b \b");
    } else {
      inputBuffer += data;
      term.write(data);
    }
  });

  term.onData((data) => {
    console.log("browser terminal received new data:", data);
    var topicName = "/device/" + deviceId + "/terminal/input";
    console.log(topicName);
    mqttc.publish(topicName, JSON.stringify({ input: data }));
  });

  const mqttc = mqtt.connect(mqttUrl, {
    username: mqtt_user,
    password: mqtt_passwd,
  });
  mqttc.subscribe("/device/" + deviceId + "/terminal/output");

  mqttc.on("message", function (topic, payload) {
    console.log(topic);
    if (topic == "/device/" + deviceId + "/terminal/output") {
      data = JSON.parse(payload);
      console.log("new output received from server:", data.output);
      term.write(data.output);
    }
  });

  mqttc.on("connect", () => {
    console.log("connected to mqtt server");
    term.writeln("Connected to MQTT server");
  });

  mqttc.on("disconnect", () => {
    console.log("disconnected from mqtt server");
    term.writeln("Disconnected from MQTT server");
  });

  function fitToscreen() {
    fit.fit();
    const dims = { cols: term.cols, rows: term.rows };
    console.log("sending new dimensions to server's pty", dims);
    mqttc.publish(
      "/device/" + deviceId + "/terminal/resize",
      JSON.stringify(dims)
    );
  }

  function debounce(func, wait_ms) {
    let timeout;
    return function (...args) {
      const context = this;
      clearTimeout(timeout);
      timeout = setTimeout(() => func.apply(context, args), wait_ms);
    };
  }

  /**
   * Handle copy and paste events
   */
  function customKeyEventHandler(e) {
    if (e.type !== "keydown") {
      return true;
    }
    if (e.ctrlKey && e.shiftKey) {
      const key = e.key.toLowerCase();
      if (key === "v") {
        // ctrl+shift+v: paste whatever is in the clipboard
        navigator.clipboard.readText().then((toPaste) => {
          term.writeText(toPaste);
        });
        return false;
      } else if (key === "c" || key === "x") {
        // ctrl+shift+x: copy whatever is highlighted to clipboard

        // 'x' is used as an alternate to 'c' because ctrl+c is taken
        // by the terminal (SIGINT) and ctrl+shift+c is taken by the browser
        // (open devtools).
        // I'm not aware of ctrl+shift+x being used by anything in the terminal
        // or browser
        const toCopy = term.getSelection();
        navigator.clipboard.writeText(toCopy);
        term.focus();
        return false;
      }
    }
    return true;
  }

  const wait_ms = 50;
  w.onresize = debounce(fitToscreen, wait_ms);
})(window);
