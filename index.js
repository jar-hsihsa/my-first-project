#!/usr/bin/env node

import Parser from 'rss-parser';
import { GoogleGenAI } from '@google/genai';
import dotenv from 'dotenv';
import pc from 'picocolors';
import ora from 'ora';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';

// Load environment variables from the project directory
const __dirname = path.dirname(fileURLToPath(import.meta.url));
dotenv.config({ path: path.join(__dirname, '.env') });

const RSS_FEED_URL = 'https://news.google.com/rss/search?q=Google+AI&hl=en-US&gl=US&ceid=US:en';
const parser = new Parser();

// Helper to draw horizontal dividers
const printDivider = () => {
  console.log(pc.gray('─'.repeat(process.stdout.columns || 80)));
};

/**
 * Validates and retrieves the Gemini API key from environment variables
 * @throws {Error} If API key is not set or invalid
 * @returns {string} The validated API key
 */
function getGeminiApiKey() {
  const apiKey = process.env.GEMINI_API_KEY;
  
  if (!apiKey) {
    return null;
  }
  
  // Validate API key format (basic check)
  if (typeof apiKey !== 'string' || apiKey.trim().length === 0) {
    throw new Error('Invalid GEMINI_API_KEY: API key must be a non-empty string');
  }
  
  return apiKey.trim();
}

async function main() {
  console.log('\n' + pc.bold(pc.bgCyan(pc.black(' ⚡ GOOGLE AI NEWS CLI '))) + ' ' + pc.cyan('Latest Updates Simplified') + '\n');

  const spinner = ora('Connecting to Google News feed...').start();

  let feed;
  try {
    feed = await parser.parseURL(RSS_FEED_URL);
  } catch (error) {
    spinner.fail(pc.red('Failed to fetch news feed. Please check your internet connection.'));
    console.error(pc.gray(error.message));
    process.exit(1);
  }

  // Get the top 8 articles
  const items = feed.items.slice(0, 8).map(item => ({
    title: item.title,
    link: item.link,
    pubDate: item.pubDate,
    source: item.source ? (typeof item.source === 'string' ? item.source : item.source.name) : 'Google News'
  }));

  if (items.length === 0) {
    spinner.warn(pc.yellow('No recent AI news found from Google.'));
    process.exit(0);
  }

  let apiKey;
  try {
    apiKey = getGeminiApiKey();
  } catch (error) {
    spinner.fail(pc.red(`Configuration error: ${error.message}`));
    process.exit(1);
  }

  if (apiKey) {
    spinner.text = 'Simplifying news into lucid language with Gemini...';
    try {
      const ai = new GoogleGenAI({ apiKey });

      const prompt = `You are an expert science communicator and AI news editor.
Analyze these recent Google AI news articles and summarize them.
Translate any complex technical jargon into extremely clear, easy-to-understand, and lucid language suitable for a beginner.
For each article, provide:
1. A simplified title.
2. A lucid summary (2-3 sentences max).
3. A key takeaway (1 sentence on why this matters).

Here is the news list:
${items.map((item, index) => `[Article #${index + 1}]
Title: ${item.title}
Source: ${item.source}
Published: ${item.pubDate}`).join('\n\n')}

Ensure the output matches the JSON schema exactly. Return exactly ${items.length} items.`;

      const response = await ai.models.generateContent({
        model: 'gemini-2.5-flash',
        contents: prompt,
        config: {
          responseMimeType: 'application/json',
          responseSchema: {
            type: 'ARRAY',
            items: {
              type: 'OBJECT',
              properties: {
                title: { type: 'STRING' },
                summary: { type: 'STRING' },
                takeaway: { type: 'STRING' }
              },
              required: ['title', 'summary', 'takeaway']
            }
          }
        }
      });

      spinner.succeed(pc.green('News simplified successfully!\n'));

      const simplifiedItems = JSON.parse(response.text);

      simplifiedItems.forEach((simplifiedItem, index) => {
        const originalItem = items[index] || {};
        
        console.log(pc.bold(pc.magenta(`${index + 1}. ${simplifiedItem.title}`)));
        console.log(pc.gray(`Source: ${originalItem.source || 'Google News'} | Date: ${originalItem.pubDate ? new Date(originalItem.pubDate).toLocaleDateString() : 'Recent'}`));
        console.log('\n' + pc.white(simplifiedItem.summary));
        console.log(pc.cyan(pc.bold('💡 Takeaway: ')) + pc.italic(pc.cyan(simplifiedItem.takeaway)));
        console.log(pc.blue(pc.underline(`Read full article: ${originalItem.link}`)));
        console.log();
        if (index < simplifiedItems.length - 1) {
          printDivider();
          console.log();
        }
      });

    } catch (error) {
      spinner.fail(pc.yellow('Failed to simplify news using Gemini API. Falling back to raw news list.'));
      console.log(pc.red(error.message));
      console.log('\n');
      renderRawNews(items);
    }
  } else {
    spinner.succeed(pc.yellow('Displaying raw news (no GEMINI_API_KEY found).\n'));
    renderRawNews(items);
    
    // Help box for setting API key
    console.log();
    console.log(pc.yellow('╭───────────────────────────────────────────────────────────────────────────────────────╮'));
    console.log(pc.yellow('│ ') + pc.bold('💡 Enable AI-powered Lucid Summaries') + '                             ' + pc.yellow('│'));
    console.log(pc.yellow('├───────────────────────────────────────────────────────────────────────────────────────┤'));
    console.log(pc.yellow('│ ') + pc.white('This tool can use Gemini to simplify these articles for you.     ') + pc.yellow('│'));
    console.log(pc.yellow('│ ') + pc.white('To enable this:') + '                                                  ' + pc.yellow('│'));
    console.log(pc.yellow('│ ') + pc.white('1. Get a free Gemini API Key from: ') + pc.cyan('https://aistudio.google.com/') + pc.yellow('  │'));
    console.log(pc.yellow('│ ') + pc.white('2. Paste your key in ') + pc.bold('.env') + pc.white(' file inside this directory:') + '            ' + pc.yellow('│'));
    console.log(pc.yellow('│    ') + pc.bold('GEMINI_API_KEY=your_key_here') + '                                  ' + pc.yellow('│'));
    console.log(pc.yellow('╰───────────────────────────────────────────────────────────────────────────────────────╯'));
    console.log();
  }
}

function renderRawNews(items) {
  items.forEach((item, index) => {
    console.log(pc.bold(pc.green(`${index + 1}. ${item.title}`)));
    console.log(pc.gray(`Source: ${item.source} | Date: ${item.pubDate ? new Date(item.pubDate).toLocaleDateString() : 'Recent'}`));
    console.log(pc.blue(pc.underline(`Link: ${item.link}`)));
    console.log();
    if (index < items.length - 1) {
      printDivider();
      console.log();
    }
  });
}

main();
