import itertools
import os
import pickle
from sympy import Eq, solve, Symbol, sympify, N
from sympy.core.sympify import SympifyError

from src.bases.engines.prototypes import QuizSolverPrototype
from src.bases.engines.data_models import LanguageDatabase
from src.constants import DATA_DIR



class QuizSolver(QuizSolverPrototype):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._language_databases = {}

        for language in [
            'english',
            'spanish',
            'portuguese',
        ]:
            filepath = os.path.join(
                DATA_DIR,
                'languages',
                language,
                'words.pkl'
            )
            with open(filepath, 'rb') as f:
                self._language_databases[language] = LanguageDatabase(**pickle.load(f))

    def solve_math(self, input_data: str) -> list[float]:
        data_input = input_data.strip().lower()

        # Type 1: Equation with '=' (solve for x)
        if '=' in data_input:
            try:
                # Split into LHS and RHS
                lhs_str, rhs_str = data_input.split('=', 1)
                lhs = sympify(lhs_str.strip())
                rhs = sympify(rhs_str.strip())
                equation = Eq(lhs, rhs)

                # Solve for x
                x = Symbol('x')
                solutions = solve(equation, x)
                return solutions
            except SympifyError:
                return "Error: Invalid equation syntax."
            except Exception as e:
                return f"Error: {str(e)}"

        # Type 2: Numerical expression (evaluate)
        else:
            try:
                expr = sympify(data_input)

                # Check for variables (unsupported in numerical evaluation)
                if expr.free_symbols:
                    return "Error: Expression contains variables."

                # Evaluate and convert to Python number
                num_expr = N(expr)
                if num_expr.is_Integer:
                    return int(num_expr)
                elif num_expr.is_real:
                    return float(num_expr)
                else:
                    return complex(num_expr)
            except SympifyError:
                return "Error: Invalid expression syntax."
            except Exception as e:
                return f"Error: {str(e)}"

    def _complete_word(self, language: str, pattern: str):
        db = self._language_databases[language]
        n = len(pattern)

        # Get all constraints (fixed letters with their positions)
        constraints = []
        for pos, char in enumerate(pattern):
            if char != '_':
                constraints.append((pos, char))

        # No constraints: return all words of this length
        if not constraints:
            return sorted(db.length_index.get(n, set()))

        # Get candidate sets for each constraint
        candidate_sets = []
        for pos, char in constraints:
            key = (n, pos, char)
            if key in db.position_index:
                candidate_sets.append(db.position_index[key])
            else:
                # If any constraint has no matches, return empty
                return []

        # Start with smallest set for efficient intersection
        candidate_sets.sort(key=len)
        candidates = candidate_sets[0]
        for s in candidate_sets[1:]:
            candidates = candidates & s  # Set intersection

        return sorted(candidates)

    def complete_words(self, language: str, pattern: str):
        words = pattern.split(' ')
        word_patterns = []
        for word in words:
            word = word.lower()
            word_patterns.append(word)

        # Solve each word pattern separately
        solutions_per_word = []
        for wp in word_patterns:
            # Convert to single-word pattern format
            solutions = self._complete_word(language, wp)
            if not solutions:
                return []
            solutions_per_word.append(solutions)

        # Generate all phrase combinations
        phrases = [' '.join(phrase) for phrase in itertools.product(*solutions_per_word)]
        return phrases

    def solve_jumbled_words(self, language: str, input_data: str) -> list[str]:
        db = self._language_databases[language]
        groups = []  # Preserve word groups

        for group in input_data.split(' '):
            groups.append(group.lower())
        # Solve each group
        solutions_per_group = []
        for group in groups:
            key = ''.join(sorted(group))
            solutions = db.anagram_index.get(key, [])
            if not solutions:
                return []  # Early termination
            solutions_per_group.append(sorted(solutions))

        return [' '.join(phrase) for phrase in itertools.product(*solutions_per_group)]
