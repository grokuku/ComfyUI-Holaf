import { app } from "../../../scripts/app.js";

// --- Constants ---
const COLS = 10;
const ROWS = 20;
const BLOCK_SIZE = 25; // Adjusted block size for node view
const UI_WIDTH = 120; // Width for the UI panel on the right
const PADDING = 10;
const BOMB_CHANCE = 0.15;
const LOCK_DELAY_DURATION = 500; // Milliseconds for lock delay

// --- Colors (approximated from CSS) ---
const COLORS = [
    null, '#FF0D72', '#0DC2FF', '#39FF14', '#F538FF',
    '#FF8E0D', '#FFE138', '#3877FF'
];
const BOMB_COLOR_INDICATOR = '#FFFFFF';
const BOMB_INDICATOR_GLOW = 'rgba(255, 255, 255, 0.7)';
const GHOST_COLOR = 'rgba(255, 255, 255, 0.35)';
const BACKGROUND_COLOR = '#050a14'; // Dark background
const GRID_COLOR_LIGHT = 'rgba(0, 255, 255, 0.08)'; // Subtle grid
const GRID_COLOR_DARK = 'rgba(0, 255, 255, 0.04)';
const TEXT_COLOR_PRIMARY = '#00ffff'; // Neon cyan
const TEXT_COLOR_SECONDARY = '#ffff00'; // Neon yellow
const TEXT_COLOR_GAMEOVER = '#FFFFFF';
const PANEL_BG_COLOR = 'rgba(0, 10, 20, 0.85)';
const BORDER_COLOR = '#00ffff';

const PIECES = [
    [], // Placeholder 0
    [[1, 1, 1], [0, 1, 0]], // T
    [[2, 2, 2, 2]],         // I
    [[0, 3, 3], [3, 3, 0]], // S
    [[4, 4, 0], [0, 4, 4]], // Z
    [[5, 0, 0], [5, 5, 5]], // L
    [[6, 6], [6, 6]],       // O
    [[0, 0, 7], [7, 7, 7]]  // J
];

// --- Game State Variables ---
let board;
let player;
let nextPiece;
let score;
let level;
let lines;
let dropCounter;
let dropInterval;
let animationFrameId = null;
let lastTime;
let gameState = 'TITLE'; // 'TITLE', 'PLAYING', 'PAUSED', 'GAME_OVER'
let isLanded = false;
let lockDelayTimer = null;
let particles = []; // For explosion effects

// --- Helper Functions ---
function createBoard() {
    return Array.from({ length: ROWS }, () => Array(COLS).fill(0));
}

function createPieceMatrix(typeId) {
    const matrix = JSON.parse(JSON.stringify(PIECES[typeId]));
    const piece = {
        matrix: matrix, typeId: typeId,
        pos: { x: 0, y: 0 }, isBomb: false, bombPos: null
    };
    if (typeId !== 6 && Math.random() < BOMB_CHANCE) { // No bombs on O piece
        piece.isBomb = true;
        let attempts = 0;
        while (piece.bombPos === null && attempts < 10) {
            const randRow = Math.floor(Math.random() * piece.matrix.length);
            const randCol = Math.floor(Math.random() * piece.matrix[0].length);
            if (piece.matrix[randRow]?.[randCol]) {
                piece.bombPos = { row: randRow, col: randCol };
            }
            attempts++;
        }
        if (piece.bombPos === null) piece.isBomb = false;
    }
    return piece;
}

function getRandomPieceType() {
    return Math.floor(Math.random() * (PIECES.length - 1)) + 1;
}

// Resets the player piece and checks for game over condition
function playerReset() {
    console.log("playerReset: Start");
    if (!nextPiece) {
        console.log("playerReset: Generating initial nextPiece");
        nextPiece = createPieceMatrix(getRandomPieceType());
    }
    player = nextPiece; // Assign the next piece to the player
    player.pos.x = Math.floor(COLS / 2) - Math.floor(player.matrix[0].length / 2);
    player.pos.y = 0; // Start at the top

    // Generate the *next* next piece for the UI display
    nextPiece = createPieceMatrix(getRandomPieceType());
    console.log("playerReset: New nextPiece generated");

    // Check for collision immediately after placing the new piece
    if (checkBoardCollision(board, player)) {
        console.log("playerReset: Game Over condition met!");
        gameState = 'GAME_OVER'; // Set game over state
        stopGameLogic(); // Stop game logic updates
    } else {
        console.log("playerReset: No immediate collision, game continues.");
    }
    console.log("playerReset: End");
}


// --- Collision and Game Logic ---
function merge(board, player) {
    if (!player) {
        console.warn("merge: Called with null player");
        return;
    }
    console.log("merge: Merging player piece");
    player.matrix.forEach((row, y) => {
        row.forEach((value, x) => {
            if (value !== 0) {
                const boardY = y + player.pos.y;
                const boardX = x + player.pos.x;
                if (boardY >= 0 && boardY < ROWS && boardX >= 0 && boardX < COLS) {
                    let blockValue = player.typeId;
                    if (player.isBomb && player.bombPos && player.bombPos.row === y && player.bombPos.col === x) {
                        blockValue += 10; // Mark as bomb
                    }
                    if (board[boardY][boardX] === 0) {
                        board[boardY][boardX] = blockValue;
                    } else {
                        // This case should ideally not happen if collision detection is correct before merge
                        console.warn("merge: Overwriting existing block at", boardX, boardY);
                        board[boardY][boardX] = blockValue;
                    }
                } else {
                     console.warn("merge: Attempted merge out of bounds at", boardX, boardY);
                }
            }
        });
    });
}

function checkBoardCollision(board, piece) {
    if (!piece || !piece.matrix) {
        // console.warn("checkBoardCollision: Called with null piece or matrix");
        return true; // Treat null piece as collision
    }
    const matrix = piece.matrix;
    const offset = piece.pos;
    for (let y = 0; y < matrix.length; ++y) {
        for (let x = 0; x < matrix[0].length; ++x) {
            if (matrix[y][x] !== 0) { // If it's part of the piece shape
                const boardY = y + offset.y;
                const boardX = x + offset.x;

                // Check boundaries
                if (boardX < 0 || boardX >= COLS || boardY >= ROWS) {
                     // console.log("Collision: Boundary", {boardX, boardY});
                     return true; // Collision with wall or floor
                }
                // Check collision with existing blocks on the board (only if within board height)
                if (boardY >= 0 && board[boardY]?.[boardX] !== 0) {
                     // console.log("Collision: Block", {boardX, boardY});
                     return true; // Collision with another block
                }
            }
        }
    }
    return false; // No collision detected
}

function rotateMatrix(matrix) {
    const rows = matrix.length; const cols = matrix[0].length;
    const newMatrix = Array.from({ length: cols }, () => Array(rows).fill(0));
    for (let y = 0; y < rows; ++y) { for (let x = 0; x < cols; ++x) { newMatrix[x][rows - 1 - y] = matrix[y][x]; } } return newMatrix;
}

function playerRotate() {
    if (!player || gameState !== 'PLAYING') return;
    const originalMatrix = player.matrix;
    const originalPos = { ...player.pos };
    const originalBombPos = player.isBomb && player.bombPos ? { ...player.bombPos } : null;

    player.matrix = rotateMatrix(player.matrix);

    // Update bomb position if it exists
    if (player.isBomb && originalBombPos) {
        const { row, col } = originalBombPos;
        const nCol = row;
        const nRow = originalMatrix[0].length - 1 - col;
        player.bombPos = { row: nRow, col: nCol };
        // Check if bomb is still within the rotated piece shape
        if (nRow < 0 || nRow >= player.matrix.length || nCol < 0 || nCol >= player.matrix[0].length || player.matrix[nRow][nCol] === 0) {
            player.isBomb = false;
            player.bombPos = null;
        }
    }

    // Wall kick logic
    let offset = 1;
    while (checkBoardCollision(board, player)) {
        player.pos.x += offset;
        offset = -(offset + (offset > 0 ? 1 : -1));
        // Limit kick distance to prevent infinite loops or excessive kicks
        if (Math.abs(offset) > player.matrix[0].length + 1) {
            // Rotation failed, revert
            player.matrix = originalMatrix;
            player.pos = originalPos;
            player.bombPos = originalBombPos;
            // Re-check bomb validity if reverted
            if (player.isBomb && player.bombPos) {
                 if (player.bombPos.row < 0 || player.bombPos.row >= player.matrix.length || player.bombPos.col < 0 || player.bombPos.col >= player.matrix[0].length || player.matrix[player.bombPos.row][player.bombPos.col] === 0) {
                     player.isBomb = false; player.bombPos = null;
                 }
            }
            return; // Exit rotation attempt
        }
    }

    // Reset lock delay if landed and rotation was successful
    if (isLanded) {
        player.pos.y++; // Temporarily check if still landed after kick
        if (!checkBoardCollision(board, player)) {
            isLanded = false; lockDelayTimer = null;
        } else {
            lockDelayTimer = Date.now(); // Reset timer
        }
        player.pos.y--; // Move back up
    }
}


function playerMove(dir) {
    if (!player || gameState !== 'PLAYING') return;
    player.pos.x += dir;
    if (checkBoardCollision(board, player)) {
        player.pos.x -= dir; return; // Revert if collision, don't reset timer
    }
    // Reset lock delay if landed and move was successful
    if (isLanded) {
        player.pos.y++;
        if (!checkBoardCollision(board, player)) { isLanded = false; lockDelayTimer = null; }
        else { lockDelayTimer = Date.now(); } // Reset timer
        player.pos.y--;
    }
}

function playerDrop() { // Soft drop
    if (!player || gameState !== 'PLAYING') return;
    player.pos.y++;
    if (checkBoardCollision(board, player)) {
        player.pos.y--;
        // Start lock delay only if not already landed/delaying
        if (!isLanded) {
            isLanded = true;
            lockDelayTimer = Date.now();
            // console.log("playerDrop: Landed, starting lock delay");
        }
    } else {
        // Piece moved down freely, reset landed state/timer
        isLanded = false;
        lockDelayTimer = null;
        dropCounter = 0; // Reset auto-drop counter on successful manual drop
        // console.log("playerDrop: Moved down freely");
    }
}

function lockPiece() {
    if (!player || gameState !== 'PLAYING') return;
    console.log("lockPiece: Start");

    merge(board, player); // Add piece to board first
    player = null; // Nullify the current player piece reference *before* potentially complex sweep/reset
    console.log("lockPiece: Player merged and nullified");

    sweepAndExplode(); // Clear lines, trigger explosions, update score/level
    console.log("lockPiece: sweepAndExplode finished");

    // Reset state variables *after* sweep
    isLanded = false;
    lockDelayTimer = null;
    dropCounter = 0;
    console.log("lockPiece: State variables reset");

    // Only reset the player piece if the game didn't end during sweep
    if (gameState !== 'GAME_OVER') {
        console.log("lockPiece: Calling playerReset");
        playerReset(); // Get the next piece and check for immediate game over
        console.log("lockPiece: playerReset finished, new gameState:", gameState);
    } else {
        console.log("lockPiece: Game is Over, not calling playerReset");
    }
    console.log("lockPiece: End");
}


function playerHardDrop() {
    if (!player || gameState !== 'PLAYING') return;
    console.log("playerHardDrop: Start");
    const startY = player.pos.y;
    const finalY = calculateGhostPosition();
    player.pos.y = finalY;

    merge(board, player); // Add piece to board
    player = null; // Nullify player reference
    console.log("playerHardDrop: Player merged and nullified");

    sweepAndExplode(); // Clear lines, trigger explosions, update score/level
    console.log("playerHardDrop: sweepAndExplode finished");

    // Reset state variables
    isLanded = false;
    lockDelayTimer = null;
    dropCounter = 0;
    console.log("playerHardDrop: State variables reset");

    // Only reset the player piece if the game didn't end during sweep
    if (gameState !== 'GAME_OVER') {
        console.log("playerHardDrop: Calling playerReset");
        playerReset();
        console.log("playerHardDrop: playerReset finished, new gameState:", gameState);
    } else {
         console.log("playerHardDrop: Game is Over, not calling playerReset");
    }
     console.log("playerHardDrop: End");
}


function sweepAndExplode() {
    console.log("sweepAndExplode: Start");
    let linesClearedThisTurn = 0;
    let explosionQueue = [];

    // --- Pass 1: Identify full lines and bombs, mark rows for clearing ---
    console.log("sweepAndExplode: Pass 1 - Identifying lines/bombs");
    for (let y = ROWS - 1; y >= 0; y--) {
        let isFull = true;
        let hasBomb = false;
        let bombX = -1;
        for (let x = 0; x < COLS; ++x) {
            if (board[y][x] === 0) {
                isFull = false; // Row isn't full
            } else if (board[y][x] > 10) { // Found a bomb
                hasBomb = true;
                bombX = x;
            }
        }
        if (isFull) {
            linesClearedThisTurn++;
            if (hasBomb) {
                explosionQueue.push({ x: bombX, y: y });
            }
            // Mark the row for clearing by setting blocks to a temporary value (-1)
            for (let x = 0; x < COLS; ++x) {
                 if (board[y][x] !== 0) board[y][x] = -1;
            }
        }
    }
    console.log("sweepAndExplode: Pass 1 - Found", linesClearedThisTurn, "lines,", explosionQueue.length, "bombs");

    // --- Pass 2: Trigger explosions (modifies board, sets blocks to 0) ---
    console.log("sweepAndExplode: Pass 2 - Triggering explosions");
    if (explosionQueue.length > 0) {
        explosionQueue.forEach(pos => {
            createExplosionEffect(pos.x, pos.y);
            triggerExplosion(pos.x, pos.y, board);
        });
    }

    // --- Pass 3: Rebuild the board without cleared lines ---
    console.log("sweepAndExplode: Pass 3 - Rebuilding board");
    if (linesClearedThisTurn > 0 || explosionQueue.length > 0) {
        let newBoard = createBoard();
        let newRowIndex = ROWS - 1;
        for (let y = ROWS - 1; y >= 0; y--) {
            // Check if the row contains any block *not* marked for clearing (-1)
            let rowShouldBeKept = false;
            for(let x = 0; x < COLS; x++) {
                if (board[y][x] > 0) { // Keep if any positive (non-bomb, non-empty, non-marked) value exists
                    rowShouldBeKept = true;
                    break;
                }
            }
            if (rowShouldBeKept) {
                if (newRowIndex >= 0) {
                     // Copy the valid blocks from the old row to the new board
                     for(let x = 0; x < COLS; x++) {
                         newBoard[newRowIndex][x] = board[y][x] > 0 ? board[y][x] : 0;
                     }
                     newRowIndex--;
                } else {
                    console.warn("sweepAndExplode: Rebuild error - newRowIndex out of bounds");
                }
            }
        }
        board = newBoard; // Replace the old board
        console.log("sweepAndExplode: Board rebuilt");
    } else {
        console.log("sweepAndExplode: No lines cleared or bombs exploded, skipping rebuild.");
    }

    // --- Update score/level/lines ---
    if (linesClearedThisTurn > 0) {
        console.log("sweepAndExplode: Updating score/level/lines");
        lines += linesClearedThisTurn;
        let s = linesClearedThisTurn === 1 ? 100 : linesClearedThisTurn === 2 ? 300 : linesClearedThisTurn === 3 ? 500 : 800;
        updateScore(s * level);
        const nl = Math.floor(lines / 10) + 1;
        if (nl > level) {
            level = nl;
            dropInterval = Math.max(1000 - (level - 1) * 75, 150);
            console.log("sweepAndExplode: Level up to", level, "New interval:", dropInterval);
        }
    }
    console.log("sweepAndExplode: End");
}


function triggerExplosion(cx, cy, b) {
    const r = 1; let destroyed = 0;
    for (let y = cy - r; y <= cy + r; ++y) {
        for (let x = cx - r; x <= cx + r; ++x) {
            if (y >= 0 && y < ROWS && x >= 0 && x < COLS) {
                // Clear block if it's not empty and not marked for line clear (-1)
                if (b[y][x] !== 0 && b[y][x] !== -1) {
                    destroyed++;
                    b[y][x] = 0; // Clear block
                }
            }
        }
    }
    updateScore(destroyed * 5 * level); // Score for destroyed blocks
}

function updateScore(amount) {
    score += amount;
}

// --- Canvas Drawing Functions ---

// Helper to lighten/darken hex colors (simplified)
function adjustColor(hex, percent) {
    hex = hex.replace(/^#/, '');
    let r = parseInt(hex.substring(0, 2), 16);
    let g = parseInt(hex.substring(2, 4), 16);
    let b = parseInt(hex.substring(4, 6), 16);

    const factor = 1 + percent / 100;
    r = Math.min(255, Math.max(0, Math.floor(r * factor)));
    g = Math.min(255, Math.max(0, Math.floor(g * factor)));
    b = Math.min(255, Math.max(0, Math.floor(b * factor)));

    return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
}


function drawBlock(ctx, x, y, colorValue, blockSize = BLOCK_SIZE, isNext = false) {
    const isBomb = colorValue > 10;
    const baseColorIndex = isBomb ? colorValue - 10 : colorValue;
    const baseColor = COLORS[baseColorIndex];
    if (!baseColor) return;

    const drawX = x * blockSize;
    const drawY = y * blockSize;

    // Simple gradient
    const gradient = ctx.createLinearGradient(drawX, drawY, drawX + blockSize, drawY + blockSize);
    gradient.addColorStop(0, adjustColor(baseColor, 15)); // Lighter
    gradient.addColorStop(1, adjustColor(baseColor, -10)); // Darker
    ctx.fillStyle = gradient;
    ctx.fillRect(drawX, drawY, blockSize, blockSize);

    // Simple border
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
    ctx.lineWidth = 1;
    ctx.strokeRect(drawX + 0.5, drawY + 0.5, blockSize - 1, blockSize - 1);

    if (isBomb && !isNext) {
        // Draw bomb indicator (simple white square)
        const bombSize = blockSize * 0.3;
        ctx.fillStyle = BOMB_COLOR_INDICATOR;
        // Simple glow effect
        ctx.shadowColor = BOMB_INDICATOR_GLOW;
        ctx.shadowBlur = 3;
        ctx.fillRect(drawX + blockSize / 2 - bombSize / 2, drawY + blockSize / 2 - bombSize / 2, bombSize, bombSize);
        ctx.shadowBlur = 0; // Reset shadow
    }
}

function drawBoardGrid(ctx, offsetX, offsetY) {
    ctx.strokeStyle = GRID_COLOR_DARK;
    ctx.lineWidth = 0.5;
    for (let x = 0; x <= COLS; x++) {
        ctx.beginPath();
        ctx.moveTo(offsetX + x * BLOCK_SIZE + 0.5, offsetY + 0.5);
        ctx.lineTo(offsetX + x * BLOCK_SIZE + 0.5, offsetY + ROWS * BLOCK_SIZE + 0.5);
        ctx.stroke();
    }
    for (let y = 0; y <= ROWS; y++) {
        ctx.beginPath();
        ctx.moveTo(offsetX + 0.5, offsetY + y * BLOCK_SIZE + 0.5);
        ctx.lineTo(offsetX + COLS * BLOCK_SIZE + 0.5, offsetY + y * BLOCK_SIZE + 0.5);
        ctx.stroke();
    }
}

function drawBoardState(ctx, offsetX, offsetY) {
    for (let y = 0; y < ROWS; ++y) {
        for (let x = 0; x < COLS; ++x) {
            if (board[y][x] !== 0) {
                drawBlock(ctx, x, y, board[y][x], BLOCK_SIZE);
            }
        }
    }
}

function calculateGhostPosition() {
    if (!player) return 0; // Return 0 if no player piece
    let ghostY = player.pos.y;
    let tempPlayer = { ...player, pos: { ...player.pos } };
    while (true) {
        tempPlayer.pos.y++;
        if (checkBoardCollision(board, tempPlayer)) {
            tempPlayer.pos.y--; break;
        }
        ghostY = tempPlayer.pos.y;
        if(tempPlayer.pos.y > ROWS + 5) { ghostY = player.pos.y; break; } // Safety break
    }
    return ghostY;
}

function drawGhostPiece(ctx, ghostY, offsetX, offsetY) {
    if (!player) return;
    ctx.globalAlpha = 0.5; // Make ghost semi-transparent
    player.matrix.forEach((row, y) => {
        row.forEach((value, x) => {
            if (value !== 0) {
                // Draw only outline for ghost
                ctx.strokeStyle = GHOST_COLOR;
                ctx.lineWidth = 2;
                ctx.strokeRect(offsetX + (player.pos.x + x) * BLOCK_SIZE + 1, offsetY + (ghostY + y) * BLOCK_SIZE + 1, BLOCK_SIZE - 2, BLOCK_SIZE - 2);
            }
        });
    });
    ctx.globalAlpha = 1.0; // Reset alpha
}


function drawPlayerPiece(ctx, offsetX, offsetY) {
    if (!player) return;
    player.matrix.forEach((row, y) => {
        row.forEach((value, x) => {
            if (value !== 0) {
                let blockValue = value;
                if (player.isBomb && player.bombPos && player.bombPos.row === y && player.bombPos.col === x) {
                    blockValue += 10; // Mark as bomb for drawing
                }
                drawBlock(ctx, player.pos.x + x, player.pos.y + y, blockValue, BLOCK_SIZE);
            }
        });
    });
}

function drawUI(ctx, uiX, uiY, uiWidth, uiHeight) {
    // Draw UI Panel Background
    ctx.fillStyle = PANEL_BG_COLOR;
    ctx.fillRect(uiX, uiY, uiWidth, uiHeight);
    ctx.strokeStyle = BORDER_COLOR;
    ctx.lineWidth = 1;
    ctx.strokeRect(uiX + 0.5, uiY + 0.5, uiWidth - 1, uiHeight - 1);

    // --- Text Styling ---
    ctx.fillStyle = TEXT_COLOR_PRIMARY;
    ctx.font = '16px Consolas, monospace';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';

    let currentY = uiY + PADDING;

    // --- Score ---
    ctx.fillText('Score:', uiX + PADDING, currentY);
    ctx.fillStyle = TEXT_COLOR_SECONDARY;
    ctx.fillText(score ?? 0, uiX + PADDING + 60, currentY); // Handle potential undefined score
    currentY += 25;

    // --- Level ---
    ctx.fillStyle = TEXT_COLOR_PRIMARY;
    ctx.fillText('Level:', uiX + PADDING, currentY);
    ctx.fillStyle = TEXT_COLOR_SECONDARY;
    ctx.fillText(level ?? 1, uiX + PADDING + 60, currentY); // Handle potential undefined level
    currentY += 25;

    // --- Lines ---
    ctx.fillStyle = TEXT_COLOR_PRIMARY;
    ctx.fillText('Lines:', uiX + PADDING, currentY);
    ctx.fillStyle = TEXT_COLOR_SECONDARY;
    ctx.fillText(lines ?? 0, uiX + PADDING + 60, currentY); // Handle potential undefined lines
    currentY += 40; // More space before next piece

    // --- Next Piece ---
    ctx.fillStyle = TEXT_COLOR_PRIMARY;
    ctx.fillText('Next:', uiX + PADDING, currentY);
    currentY += 25;

    if (nextPiece) {
        const matrix = nextPiece.matrix;
        const colorId = nextPiece.typeId;
        const matrixWidth = matrix[0].length;
        const matrixHeight = matrix.length;
        const nextBlockSize = 18; // Smaller blocks for next piece display
        // Center the piece in the available UI width
        const startX = uiX + (uiWidth - matrixWidth * nextBlockSize) / 2;
        const startY = currentY;

        matrix.forEach((row, y) => {
            row.forEach((value, x) => {
                if (value !== 0) {
                    // Use a temporary context offset for drawing the next piece
                    ctx.save();
                    ctx.translate(startX, startY);
                    drawBlock(ctx, x, y, colorId, nextBlockSize, true); // isNext = true
                    ctx.restore();
                }
            });
        });
        currentY += matrixHeight * nextBlockSize + PADDING;
    }

    // --- Controls Info ---
    currentY += 20;
    ctx.fillStyle = TEXT_COLOR_PRIMARY;
    ctx.font = '9px Consolas, monospace'; // Even smaller font for controls
    ctx.fillText('Controls:', uiX + PADDING, currentY);
    currentY += 12; // Adjust spacing for smaller font
    ctx.fillText('Arrows: Move/Rotate', uiX + PADDING, currentY);
    currentY += 12;
    ctx.fillText('Space: Hard Drop', uiX + PADDING, currentY);
    currentY += 12;
    ctx.fillText('P: Pause / Resume', uiX + PADDING, currentY); // Clarified Pause
    currentY += 12;
    ctx.fillText('Q: Quit (in Pause)', uiX + PADDING, currentY);
    currentY += 12;
    ctx.fillText('R: Reset Game', uiX + PADDING, currentY); // Added Reset info

}

function drawPauseOverlay(ctx, width, height) {
    ctx.fillStyle = 'rgba(0, 0, 0, 0.75)';
    ctx.fillRect(0, 0, width, height);

    ctx.font = 'bold 24px Consolas, monospace';
    ctx.fillStyle = TEXT_COLOR_GAMEOVER;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    const centerX = width / 2;
    const centerY = height / 2;

    ctx.fillText('Paused', centerX, centerY - 30);
    ctx.font = '16px Consolas, monospace';
    ctx.fillText('P: Resume | Q: Quit', centerX, centerY + 10);
}

function drawGameOverOverlay(ctx, width, height) {
    ctx.fillStyle = 'rgba(200, 0, 0, 0.85)';
    ctx.fillRect(0, 0, width, height);

    ctx.font = 'bold 28px Consolas, monospace';
    ctx.fillStyle = TEXT_COLOR_GAMEOVER;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    const centerX = width / 2;
    const centerY = height / 2;

    ctx.fillText('GAME OVER', centerX, centerY - 40);
    ctx.font = '20px Consolas, monospace';
    ctx.fillText(`Final Score: ${score ?? 0}`, centerX, centerY); // Handle potential undefined score
    ctx.font = '16px Consolas, monospace';
    ctx.fillText('Press Enter to Restart', centerX, centerY + 40); // Changed text
}

// --- NEW: Title Screen Drawing ---
function drawTitleScreen(ctx, width, height) {
    ctx.fillStyle = BACKGROUND_COLOR; // Use the same background
    ctx.fillRect(0, 0, width, height);

    ctx.font = 'bold 36px Consolas, monospace'; // Larger bold font for title
    ctx.fillStyle = TEXT_COLOR_PRIMARY; // Neon cyan
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    const centerX = width / 2;
    const centerY = height / 2;

    // Simple text shadow for depth
    ctx.shadowColor = 'rgba(0, 0, 0, 0.5)';
    ctx.shadowOffsetX = 2;
    ctx.shadowOffsetY = 2;
    ctx.shadowBlur = 4;
    ctx.fillText('NEUROGRID OVERLOAD', centerX, centerY - 40);
    ctx.shadowColor = 'transparent'; // Reset shadow

    ctx.font = '18px Consolas, monospace';
    ctx.fillStyle = TEXT_COLOR_SECONDARY; // Neon yellow for instruction
    ctx.fillText('Press Enter to Start', centerX, centerY + 20);
}


// --- Explosion Particles (Canvas based) ---
function createExplosionEffect(gridX, gridY) {
    const centerX = (gridX + 0.5) * BLOCK_SIZE;
    const centerY = (gridY + 0.5) * BLOCK_SIZE;
    const particleCount = 30; // Reduced count for canvas performance
    const maxLife = 800; // Life in ms

    for (let i = 0; i < particleCount; i++) {
        const angle = Math.random() * Math.PI * 2;
        const speed = Math.random() * 3 + 1; // Pixels per frame (approx)
        const life = Math.random() * (maxLife / 2) + (maxLife / 2);
        const size = Math.random() * 3 + 2;
        // Random vibrant color
        const r = 200 + Math.floor(Math.random() * 56);
        const g = 100 + Math.floor(Math.random() * 156);
        const b = Math.floor(Math.random() * 50);
        const color = `rgb(${r},${g},${b})`;

        particles.push({
            x: centerX,
            y: centerY,
            vx: Math.cos(angle) * speed,
            vy: Math.sin(angle) * speed,
            life: life,
            maxLife: life,
            size: size,
            color: color
        });
    }
}

function updateAndDrawParticles(ctx, dt) {
    for (let i = particles.length - 1; i >= 0; i--) {
        const p = particles[i];
        p.x += p.vx;
        p.y += p.vy;
        p.life -= dt;

        if (p.life <= 0) {
            particles.splice(i, 1); // Remove dead particle
        } else {
            // Draw particle
            ctx.globalAlpha = p.life / p.maxLife; // Fade out
            ctx.fillStyle = p.color;
            ctx.fillRect(p.x - p.size / 2, p.y - p.size / 2, p.size, p.size);
        }
    }
    ctx.globalAlpha = 1.0; // Reset alpha
}


// --- Main Draw Function for ComfyUI Node ---
function drawGame(node, ctx, width, height) {
    // Clear canvas
    ctx.fillStyle = BACKGROUND_COLOR;
    ctx.fillRect(0, 0, width, height);

     // Handle Title Screen separately
     if (gameState === 'TITLE') {
        drawTitleScreen(ctx, width, height);
        node.setDirtyCanvas(true, false); // Keep redrawing title if needed
        return; // Don't draw game elements on title screen
    }

    // Calculate offsets and dimensions (only needed if not title screen)
    const boardWidth = COLS * BLOCK_SIZE;
    const boardHeight = ROWS * BLOCK_SIZE;
    const boardOffsetX = PADDING;
    const boardOffsetY = PADDING;
    const uiX = boardOffsetX + boardWidth + PADDING;
    const uiY = boardOffsetY;
    const uiWidth = width - uiX - PADDING;
    const uiHeight = boardHeight;

    // Draw subtle background grid for the board area
    drawBoardGrid(ctx, boardOffsetX, boardOffsetY);

    // Draw border around the game area
    ctx.strokeStyle = BORDER_COLOR;
    ctx.lineWidth = 1;
    ctx.strokeRect(boardOffsetX - 0.5, boardOffsetY - 0.5, boardWidth + 1, boardHeight + 1); // Offset slightly for clarity

    // --- Translate context for board drawing ---
    ctx.save();
    ctx.translate(boardOffsetX, boardOffsetY);

    // Draw Board State (always draw board, even if paused/game over)
    if (board) { // Ensure board exists
        drawBoardState(ctx, 0, 0);
    }

    // Draw Ghost Piece (only if playing)
    if (gameState === 'PLAYING' && player) {
        const ghostY = calculateGhostPosition();
        if (ghostY > player.pos.y) {
            drawGhostPiece(ctx, ghostY, 0, 0);
        }
    }

    // Draw Player Piece (only if playing)
    if (gameState === 'PLAYING' && player) {
        drawPlayerPiece(ctx, 0, 0);
    }

    // Draw Particles
    updateAndDrawParticles(ctx, 16); // Assuming ~60fps, dt=16ms

    // --- Restore context translation ---
    ctx.restore(); // Restore translation *before* drawing UI

    // Draw UI Panel (always draw UI if not title screen)
    drawUI(ctx, uiX, uiY, uiWidth, uiHeight);

    // Draw Overlays / Screens based on gameState
    // Note: Game elements (board, player, UI) are drawn *before* this switch if needed
    switch (gameState) {
        // case 'TITLE': // Handled above
        //     break;
        case 'PAUSED':
            drawPauseOverlay(ctx, width, height);
            break;
        case 'GAME_OVER':
            drawGameOverOverlay(ctx, width, height);
            break;
        case 'PLAYING':
            // No overlay needed for playing state
            break;
    }

    // Request next frame from ComfyUI (always needed while node is visible for drawing)
    node.setDirtyCanvas(true, false);
}


// --- Game Loop ---
function update(time = 0) {
    // Loop should always request the next frame to handle drawing updates for any state
    // unless explicitly stopped (e.g., on node removal)
    if (animationFrameId) { // Check if loop should continue
        animationFrameId = requestAnimationFrame(update);
    } else {
        // If animationFrameId is null (e.g., after node removal), stop requesting frames
        console.log("update: animationFrameId is null, stopping loop.");
        return;
    }

    // Only run game logic if PLAYING
    if (gameState === 'PLAYING') {
        const dt = time - (lastTime || time);
        lastTime = time;

        // Handle lock delay timer
        if (isLanded && lockDelayTimer !== null) {
            if (Date.now() - lockDelayTimer > LOCK_DELAY_DURATION) {
                // console.log("update: Lock delay expired, calling lockPiece");
                lockPiece(); // This might change gameState to GAME_OVER
            }
        } else if (player) { // Ensure player exists before trying to drop
            // Only auto-drop if not currently in lock delay phase
            dropCounter += dt;
            if (dropCounter > dropInterval) {
                // console.log("update: Auto-dropping piece");
                playerDrop(); // Checks collision and may start lock delay
            }
        }
    } else {
         // If not playing, reset lastTime to avoid large dt jump when resuming/restarting
         lastTime = time;
    }
} // End of update function


// --- Game Initialization and Control ---
// Initializes variables, called by startGame or reset
function initializeGameState() {
    console.log("initializeGameState: Resetting state");
    board = createBoard();
    score = 0; level = 1; lines = 0;
    dropCounter = 0; dropInterval = 1000; lastTime = 0;
    isLanded = false; lockDelayTimer = null;
    particles = []; // Clear particles
    nextPiece = null; // Ensure new piece is generated
    player = null; // Reset player
    // Don't set gameState here, let the caller decide
}

// Starts the actual game playing state and loop
function startGame(node) {
    console.log("startGame called");
    initializeGameState(); // Set up board, score etc.
    playerReset(); // Generate first player piece and next piece

    // Check if game over immediately after reset
    if (gameState === 'GAME_OVER') {
         console.log("Game over immediately on start");
         node.setDirtyCanvas(true, false); // Draw game over screen
         return;
    }

    gameState = 'PLAYING'; // Set state to playing *after* reset checks

    // Start the game loop's logic execution if not already running
    if (animationFrameId === null) {
        console.log("Starting animation frame loop via startGame");
        lastTime = performance.now();
        animationFrameId = requestAnimationFrame(update);
    } else {
        console.log("Animation frame loop already running, resetting time.");
        lastTime = performance.now(); // Ensure time is reset for dt calculation
    }
    node.setDirtyCanvas(true, false); // Trigger initial draw of playing state
}


function stopGameLogic() {
    // This function stops the game logic part of the update loop
    // but allows the animationFrame loop to continue for drawing overlays
    console.log("Game logic stopped (drawing loop may continue)");
    // We don't cancel animationFrameId here, drawing should continue
}

function togglePause() {
    if (gameState === 'PLAYING') {
        gameState = 'PAUSED';
        console.log("Game Paused");
        // Logic stops in update() based on gameState
    } else if (gameState === 'PAUSED') {
        gameState = 'PLAYING';
        lastTime = performance.now(); // Reset time to avoid large jump
        console.log("Game Resumed");
        // Ensure animation loop is running if it somehow stopped
        if (animationFrameId === null) { // Should not happen if drawing loop continues
             console.log("Restarting animation frame loop on unpause");
             animationFrameId = requestAnimationFrame(update);
        }
    }
    // Drawing update is handled by onDrawBackground triggering drawGame
}

function quitGame(node) {
    if (gameState !== 'PAUSED') return; // Only quit from pause menu
    gameState = 'GAME_OVER'; // Go to game over screen on quit
    stopGameLogic(); // Stop game logic updates
    // Redraw to show game over screen
    node.setDirtyCanvas(true, false);
}


// --- ComfyUI Node Integration ---
app.registerExtension({
    name: "Holaf-Nodes.NeurogridOverloadGame",
    async nodeCreated(node) {
        if (node.comfyClass === "HolafNeurogridOverload") {

            // Removed button widget

            // --- Keyboard Listener ---
            const handleKeyDown = (event) => {
                // Only process keys if the node is visible
                 if (node.flags.collapsed) return;

                const key = event.key.toLowerCase();

                // --- Handle Start/Restart ---
                if (key === 'enter') {
                    if (gameState === 'TITLE' || gameState === 'GAME_OVER') {
                        event.preventDefault();
                        event.stopPropagation();
                        console.log("Enter pressed - Starting/Restarting game");
                        startGame(node);
                        node.setDirtyCanvas(true, false); // Explicit redraw request AFTER startGame
                        return;
                    }
                }

                // --- Handle Reset ---
                if (key === 'r') {
                    event.preventDefault();
                    event.stopPropagation();
                    console.log("R pressed - Resetting to Title");
                    initializeGameState(); // Reset variables only
                    playerReset(); // Get first pieces
                    gameState = 'TITLE'; // Go back to title screen
                    stopGameLogic(); // Stop game logic if it was running
                    node.setDirtyCanvas(true, false); // Redraw title screen
                    return;
                }

                // --- Handle Pause/Quit (only when playing or paused) ---
                 if (gameState === 'PLAYING' || gameState === 'PAUSED') {
                    if (key === 'p') {
                        event.preventDefault();
                        event.stopPropagation();
                        togglePause();
                        node.setDirtyCanvas(true, false); // Redraw pause/play state
                        return;
                    }
                    if (key === 'q' && gameState === 'PAUSED') { // Quit only works if paused
                        event.preventDefault();
                        event.stopPropagation();
                        quitGame(node);
                        // quitGame calls setDirtyCanvas
                        return;
                    }
                 }

                // --- Handle Gameplay Controls (only when playing) ---
                if (gameState === 'PLAYING') {
                    // Use only arrow keys and space
                    if (['arrowleft', 'arrowright', 'arrowdown', 'arrowup', ' '].includes(key)) {
                         event.preventDefault();
                         event.stopPropagation();
                         switch (key) {
                            case 'arrowleft': playerMove(-1); break;
                            case 'arrowright': playerMove(1); break;
                            case 'arrowdown': playerDrop(); break; // Soft drop
                            case 'arrowup': playerRotate(); break;
                            case ' ': playerHardDrop(); break; // Hard drop
                         }
                         node.setDirtyCanvas(true, false); // Update display after action
                         return; // Handled
                    }
                }

                // If key wasn't handled above, ignore it
            };

            // Attach listener to the document (using capture phase is important)
            document.addEventListener('keydown', handleKeyDown, true);

            // Cleanup listener when node is removed
            const onRemoved = node.onRemoved; // Store original onRemoved
            node.onRemoved = () => { // Define new onRemoved
                console.log("Removing keydown listener and stopping game loop for Tetris node");
                document.removeEventListener('keydown', handleKeyDown, true);
                stopGameLogic(); // Ensure game logic stops
                if (animationFrameId) { // Also cancel animation frame on removal
                    cancelAnimationFrame(animationFrameId);
                    animationFrameId = null;
                    console.log("Animation frame cancelled");
                }
                onRemoved?.(); // Call original onRemoved if it existed
            };

            // --- Drawing ---
            const onDrawBackground = node.onDrawBackground;
            node.onDrawBackground = function(ctx) {
                onDrawBackground?.apply(this, arguments); // Call original background draw
                if (!this.flags.collapsed) {
                    // Pass node instance, context, and calculated size
                    // Ensure game state variables are accessible for drawing
                    if (!board) { // Initialize board if it doesn't exist yet for title screen drawing
                         initializeGameState(); // Set initial scores etc.
                         board = createBoard(); // Create board for background drawing
                    }
                    drawGame(node, ctx, this.size[0], this.size[1]);
                }
            };

            // Set fixed size and prevent resizing if possible
            const calculatedWidth = COLS * BLOCK_SIZE + UI_WIDTH + PADDING * 3;
            const calculatedHeight = ROWS * BLOCK_SIZE + PADDING * 2;
            node.setSize([calculatedWidth, calculatedHeight]);
            node.resizable = false; // Attempt to disable resizing

            // Initialize game state to show Title Screen
            gameState = 'TITLE';
            initializeGameState(); // Set initial scores etc.
            board = createBoard(); // Create board for background drawing
            // Start the animation loop for drawing immediately (needed for title screen)
            if (animationFrameId === null) {
                 console.log("Starting drawing loop for Title Screen on node creation");
                 animationFrameId = requestAnimationFrame(update);
            }
            node.setDirtyCanvas(true, false); // Draw initial title screen
        }
    }
});
