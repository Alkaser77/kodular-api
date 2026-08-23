const express = require('express');
const { v4: uuidv4 } = require('uuid');
const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.urlencoded({ extended: true }));
app.use(express.json());

let users = {};

app.post('/check', (req, res) => {
  const { user_id, hours } = req.body;
  const h = parseInt(hours) || 24;
  if (!users[user_id]) {
    const key = uuidv4().slice(0, 8);
    users[user_id] = { key, expire: Date.now() + h * 3600000 };
    return res.json({ status: "new", key: key, expire: users[user_id].expire });
  }
  if (Date.now() < users[user_id].expire) {
    return res.json({ status: "active", key: users[user_id].key, expire: users[user_id].expire });
  }
  return res.json({ status: "wait", message: "لازم تست 24 ساعة" });});app.get('/', (req, res) => res.send('Kodular API is Running'));app.listen(PORT, () => console.log(`API Server running on port ${PORT}`));
