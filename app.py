"""Flask application for jetlag-forge.

Local-first: everything runs on your machine, nothing is uploaded, no API
keys are needed. The SQLite database holds your own saved trip plans so
you can come back to them.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone

from flask import Flask, jsonify, request, send_from_directory

from engine import analyze, PROFILES
from engine.export import to_markdown, to_json
from engine.parse import BriefError
from engine.samples import list_samples, get_sample

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'data', 'journeys.db')

app = Flask(__name__, static_folder='static', static_url_path='/static')


# --------------------------------------------------------------- storage


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        """CREATE TABLE IF NOT EXISTS journeys (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               title TEXT NOT NULL,
               profile TEXT NOT NULL DEFAULT 'balanced',
               brief TEXT NOT NULL,
               report TEXT NOT NULL,
               score REAL NOT NULL,
               band TEXT NOT NULL,
               rating INTEGER,
               notes TEXT,
               created_at TEXT NOT NULL
           )"""
    )
    conn.commit()
    conn.close()


init_db()


def row_to_summary(row):
    return {
        'id': row['id'],
        'title': row['title'],
        'profile': row['profile'],
        'score': row['score'],
        'band': row['band'],
        'rating': row['rating'],
        'notes': row['notes'],
        'created_at': row['created_at'],
    }


# ---------------------------------------------------------------- routes


@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'version': '1.0.0'})


@app.route('/api/profiles')
def profiles():
    return jsonify([
        {'id': key, 'label': value['label'], 'blurb': value['blurb']}
        for key, value in PROFILES.items()
    ])


@app.route('/api/samples')
def samples():
    return jsonify(list_samples())


@app.route('/api/samples/<sample_id>')
def sample_detail(sample_id):
    sample = get_sample(sample_id)
    if not sample:
        return jsonify({'error': 'sample not found'}), 404
    return jsonify(sample)


@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    data = request.get_json(silent=True) or {}
    brief = data.get('brief', '')
    profile = data.get('profile', 'balanced')
    try:
        report = analyze(brief, profile)
    except BriefError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:  # pragma: no cover - defensive
        return jsonify({'error': 'analysis failed: %s' % exc}), 500
    return jsonify(report)


@app.route('/api/journeys', methods=['POST'])
def save_journey():
    data = request.get_json(silent=True) or {}
    brief = data.get('brief', '')
    profile = data.get('profile', 'balanced')
    try:
        report = analyze(brief, profile)
    except BriefError as exc:
        return jsonify({'error': str(exc)}), 400
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO journeys (title, profile, brief, report, score, band, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (report['meta']['title'] or 'Untitled trip', profile, brief,
         to_json(report), report['score']['overall'], report['score']['band'],
         datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({'id': new_id, 'score': report['score']['overall']}), 201


@app.route('/api/journeys')
def list_journeys():
    conn = get_db()
    rows = conn.execute(
        """SELECT id, title, profile, score, band, rating, notes, created_at
           FROM journeys ORDER BY id DESC LIMIT 100"""
    ).fetchall()
    conn.close()
    return jsonify([row_to_summary(r) for r in rows])


@app.route('/api/journeys/<int:journey_id>')
def get_journey(journey_id):
    conn = get_db()
    row = conn.execute('SELECT * FROM journeys WHERE id = ?', (journey_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({'error': 'journey not found'}), 404
    return jsonify({
        'id': row['id'],
        'title': row['title'],
        'profile': row['profile'],
        'brief': row['brief'],
        'report': json.loads(row['report']),
        'rating': row['rating'],
        'notes': row['notes'],
        'created_at': row['created_at'],
    })


@app.route('/api/journeys/<int:journey_id>', methods=['PATCH'])
def update_journey(journey_id):
    data = request.get_json(silent=True) or {}
    conn = get_db()
    row = conn.execute('SELECT * FROM journeys WHERE id = ?', (journey_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'journey not found'}), 404
    rating = data.get('rating', row['rating'])
    notes = data.get('notes', row['notes'])
    conn.execute(
        'UPDATE journeys SET rating = ?, notes = ? WHERE id = ?',
        (rating, notes, journey_id),
    )
    conn.commit()
    conn.close()
    return jsonify({'id': journey_id, 'rating': rating, 'notes': notes})


@app.route('/api/journeys/<int:journey_id>/export')
def export_journey(journey_id):
    fmt = request.args.get('fmt', 'md')
    conn = get_db()
    row = conn.execute('SELECT * FROM journeys WHERE id = ?', (journey_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({'error': 'journey not found'}), 404
    report = json.loads(row['report'])
    if fmt == 'json':
        return send_from_directory(
            app.static_folder, 'index.html') if False else app.response_class(
            to_json(report), mimetype='application/json',
            headers={'Content-Disposition': 'attachment; filename=jetlag-%d.json' % journey_id})
    return app.response_class(
        to_markdown(report), mimetype='text/markdown',
        headers={'Content-Disposition': 'attachment; filename=jetlag-%d.md' % journey_id})


@app.route('/api/export', methods=['POST'])
def export_now():
    data = request.get_json(silent=True) or {}
    brief = data.get('brief', '')
    profile = data.get('profile', 'balanced')
    fmt = data.get('fmt', 'md')
    try:
        report = analyze(brief, profile)
    except BriefError as exc:
        return jsonify({'error': str(exc)}), 400
    if fmt == 'json':
        return app.response_class(
            to_json(report), mimetype='application/json',
            headers={'Content-Disposition': 'attachment; filename=jetlag-plan.json'})
    return app.response_class(
        to_markdown(report), mimetype='text/markdown',
        headers={'Content-Disposition': 'attachment; filename=jetlag-plan.md'})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '5000'))
    app.run(host='127.0.0.1', port=port, debug=False)
