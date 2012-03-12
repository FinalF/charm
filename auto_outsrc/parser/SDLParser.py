# batch parser provides majority of the functionality for parsing bv files and the mechanics of the 
# techniques for generating an optimized batch equation (tech 2, 3, 4 and simplifying products, etc.)
# 

from pyparsing import *
from SDLang import *
from VarInfo import *
from ForLoop import *
import string,sys

objStack = []
currentFuncName = NONE_FUNC_NAME
ASSIGN_KEYWORDS = ['input', 'output']
assignInfo = {}
forLoops = {}
varDepList = {}
varInfList = {}
varsThatProtectM = {}
varTypes = {}
algebraicSetting = None
startLineNo_ForLoop = None
TYPE, CONST, PRECOMP, OTHER, TRANSFORM = 'types', 'constant', 'precompute', 'other', 'transform'
ARBITRARY_FUNC = 'func:'
MESSAGE, SIGNATURE, PUBLIC, LATEX, SETTING = 'message','signature', 'public', 'latex', 'setting'
# qualifier (means only one instance of that particular keyword exists)
SAME, DIFF = 'one', 'many'

def createNode(s, loc, toks):
    print('createNode => ', toks)
    return BinaryNode(toks[0])

# convert 'attr < value' to a binary tree based on 'or' and 'and'
def parseNumConditional(s, loc, toks):
    print("print: %s" % toks)
    return BinaryNode(toks[0])

def debugParser(s, loc, toks):
    print("debug info: %s" % toks)
    return toks
        
def pushFirst( s, loc, toks ):
    if debug >= levels.some:
       print("Pushing first =>", toks[0])
    objStack.append( toks[0] )

def pushSecond(s, loc, toks ):
    if debug >= levels.some: print("Pushing second => ", toks)
    objStack.append( toks[0] )

def checkCount(s, loc, toks):
    cnt = len(toks)
    objStack.append( str(cnt) )

def pushFunc(s, loc, toks):
    if debug >= levels.some: print("found a function: ", toks[0])
    objStack.append( FUNC_SYMBOL + toks[0] )

# Implements language parser for our signature descriptive language (SDL) and returns
# a binary tree (AST) representation of valid SDL statements.
class SDLParser:
    def __init__(self, verbose=False):
        self.finalPol = self.getBNF()
        self.verbose = verbose

    def getBNF(self):
        AndOp = Literal("and")
        lpar = Literal("(").suppress() | Literal("{").suppress()
        rpar = Literal(")").suppress() | Literal("}").suppress()
        rcurly = Literal("}").suppress()
        
        Comment = Literal("#") + restOfLine
        MulOp = Literal("*")
        DivOp = Literal("/")
        Concat = Literal("|")
        ExpOp = Literal("^")
        AddOp = Literal("+")
        SubOp = Literal("-")        
        Equality = Literal("==") # | Word("<>", max=1)
        Assignment =  Literal(":=")
        Pairing = Literal("e(") # Pairing token
        Hash = Literal("H(") # TODO: provide a way to specify arbitrary func. calls
        Random = Literal("random(")
        Prod = Literal("prod{") # dot product token
        For = Literal("for{")
        Sum = Literal("sum{")
        ProdOf = Literal("on")
        ForDo = Literal("do") # for{x,y} do y
        SumOf = Literal("of")
        List  = Literal("list{") # represents a list
        MultiLine = Literal(";") + Optional(Literal("\\n").suppress())
        funcName = Word(alphanums + '_')
        blockName = Word(alphanums + '_:')
        BeginAndEndBlock = CaselessLiteral(START_TOKEN) | CaselessLiteral(END_TOKEN)
        BlockSep   = Literal(BLOCK_SEP)

        # captures the binary operators allowed (and, ^, *, /, +, |, ==)        
        BinOp = MultiLine | AndOp | ExpOp | MulOp | DivOp | SubOp | AddOp | Concat | Equality
        # captures order of parsing token operators
        Token = Equality | AndOp | ExpOp | MulOp | DivOp | SubOp | AddOp | ForDo | ProdOf | SumOf | Concat | Assignment | MultiLine
        Operator = Token 
        #Operator = OperatorAND | OperatorOR | Token

        # describes an individual leaf node
        leafNode = Word(alphanums + '_-#\\?').setParseAction( createNode )
        expr = Forward()
        term = Forward()
        factor = Forward()
        atom = (BeginAndEndBlock + BlockSep + blockName.setParseAction( pushSecond ) ).setParseAction( pushFirst ) | \
               (Hash + expr + ',' + expr + rpar).setParseAction( pushFirst ) | \
               (Pairing + expr + ',' + expr + rpar).setParseAction( pushFirst ) | \
               (Prod + expr + ',' + expr + rcurly).setParseAction( pushFirst ) | \
               (For + expr + ',' + expr + rcurly).setParseAction( pushFirst ) | \
               (Sum + expr + ',' + expr + rcurly).setParseAction( pushFirst ) | \
               (Random + leafNode + rpar).setParseAction( pushFirst ) | \
               (List + delimitedList(leafNode).setParseAction( checkCount ) + rcurly).setParseAction( pushFirst ) | \
               (funcName + '(' + delimitedList(leafNode).setParseAction( checkCount ) + ')').setParseAction( pushFunc ) | \
               lpar + expr + rpar | (leafNode).setParseAction( pushFirst )

        # Represents the order of operations (^, *, |, ==)
        # Place more value on atom [ ^ factor}, so gets pushed on the stack before atom [ = factor], right?
        # In other words, adds order of precedence to how we parse the string. This means we are parsing from right
        # to left. a^b has precedence over b = c essentially
        #factor << atom + ZeroOrMore( ( ExpOp + factor ).setParseAction( pushFirst ) )
        factor << atom + ZeroOrMore( ( BinOp + factor ).setParseAction( pushFirst ) )
        
        term = atom + ZeroOrMore((Operator + factor).setParseAction( pushFirst ))
        # define placeholder set earlier with a 'term' + Operator + another term, where there can be
        # more than zero or more of the latter. Once we find a term, we first push that into
        # the stack, then if ther's an operand + term, then we first push the term, then the Operator.
        # so on and so forth (follows post fix notation).
        expr << term + ZeroOrMore((Operator + term).setParseAction( pushFirst ))
        # final bnf object
        finalPol = expr#.setParseAction( debugParser )
        finalPol.ignore( Comment )
        return finalPol
    
    # method for evaluating stack assumes operators have two operands and pops them accordingly
    def evalStack(self, stack, line_number):
        op = stack.pop()
        if debug >= levels.some:
            print("op: %s" % op)
        if op in ["+","-","*", "/","^", ":=", "==", "e(", "for{", "do","prod{", "on", "sum{", "of", "|", "and", ";"]:
            op2 = self.evalStack(stack, line_number)
            op1 = self.evalStack(stack, line_number)
            return createTree(op, op1, op2)
        elif op in ["H("]:
            op2 = self.evalStack(stack, line_number)
            op1 = self.evalStack(stack, line_number)
            return createTree(op, op1, op2)
        elif op in ["list{"]:
            ops = []
            cnt = self.evalStack(stack, line_number)
#            print("count: ", cnt)
            for i in range(int(cnt)):
                ops.append(self.evalStack(stack, line_number))
            newList = createTree(op, None, None)
            ops.reverse()
            newList.listNodes = list(ops)
            return newList
        elif op in ["random("]:
            op1 = self.evalStack(stack, line_number)
            return createTree(op, op1, None)
        elif FUNC_SYMBOL in op:
            ops = []
            cnt = self.evalStack(stack, line_number)
            if self.verbose: print("func name: ", op.split(FUNC_SYMBOL)[1])
            for i in range(int(cnt)):
                ops.append(self.evalStack(stack, line_number))
            newList = createTree(op, None, None, op.split(FUNC_SYMBOL)[1])
            ops.reverse()
            newList.listNodes = list(ops)
            return newList
        elif op in [START_TOKEN, END_TOKEN]: # start and end block lines
            op1 = self.evalStack(stack, line_number)
            global currentFuncName, forLoops, startLineNo_ForLoop
            if (op1.startswith(DECL_FUNC_HEADER) == True):
                if (op == START_TOKEN):
                    currentFuncName = op1[len(DECL_FUNC_HEADER):len(op1)]
                elif (op == END_TOKEN):
                    currentFuncName = NONE_FUNC_NAME
            elif (op1 == TYPES_HEADER):
                if (op == START_TOKEN):
                    currentFuncName = TYPES_HEADER
                elif (op == END_TOKEN):
                    currentFuncName = NONE_FUNC_NAME
            elif (op1 == FOR_LOOP_HEADER):
                if (op == START_TOKEN):
                    startLineNo_ForLoop = line_number
                elif (op == END_TOKEN):
                    startLineNo_ForLoop = None
                    lenForLoops = len(forLoops[currentFuncName])
                    if (forLoops[currentFuncName][lenForLoops - 1].getEndLineNo() != None):
                        sys.exit("Ending line number of one of the for loops was set prematurely.")
                    forLoops[currentFuncName][lenForLoops - 1].setEndLineNo(int(line_number))
            return createTree(op, op1, None)
        else:
            # Node value
            return op
    
    # main loop for parser. 1) declare new stack, then parse the string (using defined BNF) to extract all
    # the tokens from the string (not used for anything). 3) evaluate the stack which is in a post
    # fix format so that we can pop an OR, AND, ^ or = nodes then pull 2 subsequent variables off the stack. Then,
    # recursively evaluate those variables whether they are internal nodes or leaf nodes, etc.
    def parse(self, line, line_number=0):
        # use lineCtr to track line of code.
        global objStack
        del objStack[:]
        try:
            tokens = self.finalPol.parseString(line)
            if debug >= levels.some:
                print("stack =>", objStack)
            object = self.evalStack(objStack, line_number)
            if len(objStack) > 0 or object == False:
                raise TypeError("Invalid SDL Expression!")
            return object
        except:
            print("Invalid SDL Expression found at line #%d: '%s'" % (line_number, line))
            exit(-1)
        if len(objStack) > 0:
            raise TypeError("Invalid SDL Expression!")
        return None

# valid keywords
signer_mode  = Enum('single', 'multi', 'ring')
LINE_DELIM, COMMENT = ';', '#'


def clean(arr):
    return [i.strip() for i in arr]

def handle(lines, target):
    if target == LATEX:
        code = {}; EQ = ':='
        for line in lines:
            line = line.rstrip()
            if line.find(EQ) != -1:
                x = line.split(EQ)
                lhs, rhs = x[0].strip(), x[1].strip()
                code [ lhs ] = rhs
        print("latex =>", code)
        return code
    
    # parse as usual
    parser = BatchParser()
    if type(lines) != list:
        return parser.parse(lines)

    if (target in [CONST, TRANSFORM, PUBLIC, SIGNATURE, MESSAGE]) or (ARBITRARY_FUNC in target):
        # parse differently 'a, b, etc.\n'
        _ast = []
        for line in lines:
            l = line.split(',')
            _ast = [i.strip() for i in l]
        print(target, " =>", _ast)
        return _ast
    elif target == TYPE:
        _ast = {}
        for line in lines:
            ast_node = parser.parse(line)
            # make sure it's an assignment node
            # otherwise, ignore the node
            if ast_node.type == ops.EQ:
                left = str(ast_node.left)
                right = str(ast_node.right)
                _ast[ left ] = right
        print(target, " =>", _ast)
        return _ast
    elif target == PRECOMP:
        indiv_ast = {}
        batch_ast = {}
        for line in lines:
            ast_node = parser.parse(line)
            # make sure it's an assignment node
            # otherwise, ignore the node
            if ast_node.type == ops.EQ:
                left = ast_node.left
                right = ast_node.right
                indiv_ast[ left ] = right
                batch_ast[ BinaryNode.copy(left) ] = BinaryNode.copy(right)
        #print(target, " =>", indiv_ast)
        return (indiv_ast, batch_ast)
    return None

debugs = levels.none

def parseFile(filename):
    fd = open(filename, 'r')
    ast = {TYPE: None, CONST: None, PRECOMP: None, TRANSFORM: None, 
           MESSAGE: None, SIGNATURE: None, PUBLIC: None, LATEX: None, 
           OTHER: [] }
    AcceptedEnclosures = [TYPE, CONST, PRECOMP, TRANSFORM, MESSAGE, SIGNATURE, PUBLIC, LATEX]
    # parser = BatchParser()
    code = fd.readlines(); i = 1
    inStruct = (False, None)
    queue = []
    for line in code:
        if len(line.strip()) == 0 or line[0] == COMMENT:
            continue
        elif line.find(BLOCK_SEP) != -1: # parse differently
            token = clean(line.split(BLOCK_SEP))
            if token[0] == START_TOKEN and (token[1] in AcceptedEnclosures or ARBITRARY_FUNC in token[1]):
                inStruct = (True, token[1])
                if debugs == levels.all: print("Got a section!!!")
                continue
            elif inStruct[0]:
                # continue until we reach an end token, then
                # test if end token matches the start token, if so can handle queue 
                key = token[1]
                if token[0] == END_TOKEN and inStruct[1] == key:
                    ast[ key ] = handle(queue, key)
                    if debugs == levels.all:
                        print("section =>", key)
                        # print("queue =>", queue)
                        # print("result =>", ast[key])
                    # check for global syntax error and exit
                    queue = [] # tmp remove everything
                    inStruct = (False, None)  
            else:
                print("Syntax Error while parsing section: ", line)

        else: # if not, keep going and assume that we can safely add lines to queue
            if inStruct[0]:
                if line.find(LINE_DELIM) != -1: # if a ';' exists in string then we can probably split into two
                    queue.extend(line.split(LINE_DELIM))
                else:
                    queue.append(line)
            elif len(line.strip()) == 0 or line[0] == COMMENT:
                if debugs == levels.all:
                    print(line)
                continue
            else:
                if debugs == levels.all: 
                    print("Not in a type enclosure: ", line)
                result = handle(line, None)
                #print("result =>", result)
                #print("type =>", type(result))
                ast[ OTHER ].append(result)                
                
    fd.close()
    return ast

def updateVarTypes(varTypeSubStruct, varName, type):
    if ( (varName in varTypeSubStruct) and (varTypeSubStruct[varName] != type) ):
        sys.exit("Found mismatching type information in cryptoscheme.")

    if (isValidType(type) == False):
        sys.exit("Type inference engine found type that is not one of the currently supported types.")

    varTypeSubStruct[varName] = type

def checkPairingInputTypes_Symmetric(leftType, rightType):
    if ( (leftType != types.G1) and (leftType != types.G2) ):
        sys.exit("Problem with the left side of one of the pairings in the symmetric setting.")

    if ( (rightType != types.G1) and (rightType != types.G2) ):
        sys.exit("Problem with the right side of one of the pairings in the symmetric setting.")

def checkPairingInputTypes_Asymmetric(leftType, rightType):
    if (leftType != types.G1):
        sys.exit("One of the pairings in the asymmetric setting does not have a left side of type " + str(types.G1))

    if (rightType != types.G2):
        sys.exit("One of the pairings in the asymmetric setting does not have a right side of type " + str(types.G2))

def checkPairingInputTypes(node):
    if (node.type != ops.PAIR):
        sys.exit("checkPairingInputTypes in SDLParser was passed a node that is not of type " + str(ops.PAIR))

    leftType = getVarTypeInfoRecursive(node.left)
    rightType = getVarTypeInfoRecursive(node.right)

    if (algebraicSetting == SYMMETRIC_SETTING):
        checkPairingInputTypes_Symmetric(leftType, rightType)
    elif (algebraicSetting == ASYMMETRIC_SETTING):
        checkPairingInputTypes_Asymmetric(leftType, rightType)
    else:
        sys.exit("Algebraic setting is set to unsupported value (found in checkPairingInputTypes in SDLParser).")

def getVarNameEntryFromAssignInfo(varName):
    retFuncName = None
    retVarInfoObj = None

    for funcName in assignInfo:
        for currentVarName in assignInfo[funcName]:
            if (currentVarName == varName):
                if ( (retVarInfoObj != None) or (retFuncName != None) ):
                    if ( (funcName != TYPES_HEADER) and (retFuncName != TYPES_HEADER) ):
                        sys.exit("getVarNameEntryFromAssignInfo in SDLParser.py found multiple assignments of the same variable is assignInfo in which neither of the functions is " + str(TYPES_HEADER))
                    if (funcName == TYPES_HEADER):
                        retFuncName = funcName
                        retVarInfoObj = assignInfo[funcName][currentVarName]
                else:
                    retFuncName = funcName
                    retVarInfoObj = assignInfo[funcName][currentVarName]

    if ( (retVarInfoObj == None) or (retFuncName == None) ):
        sys.exit("getVarNameEntryFromAssignInfo in SDLParser.py could not locate entry in assignInfo of the name passed in.")

    return (retFuncName, retVarInfoObj)

def getNextListName(origListName, index):
    (listFuncNameInAssignInfo, listEntryInAssignInfo) = getVarNameEntryFromAssignInfo(origListName)
    if ( (listEntryInAssignInfo.getIsList() == False) or (len(listEntryInAssignInfo.getListNodesList()) == 0) ):
        sys.exit("Problem with list obtained from assignInfo in getNextListName in SDLParser.")

    listNodesList = listEntryInAssignInfo.getListNodesList()
    return (listFuncNameInAssignInfo, listNodesList[int(index)])

def getVarNameFromListIndices(node):
    if (node.type != ops.ATTR):
        sys.exit("Node passed to getVarNameFromListIndex in SDLParser is not of type " + str(ops.ATTR))

    if (node.attr.find(LIST_INDEX_SYMBOL) == -1):
        sys.exit("Node passed to getVarNameFromListIndex is not a reference to an index in a list.")

    nodeName = node.attr
    nodeNameSplit = nodeName.split(LIST_INDEX_SYMBOL)
    currentListName = nodeNameSplit[0]
    nodeNameSplit.remove(currentListName)

    for listIndex in nodeNameSplit:
        if (listIndex.isdigit() == False):
            return (None, None)
        (currentFuncName, currentListName) = getNextListName(currentListName, listIndex)

    return (currentFuncName, currentListName)

def getVarTypeInfoRecursive(node):
    if (node.type == ops.RANDOM):
        return node.left.attr
    if (node.type == ops.EXP):
        return getVarTypeInfoRecursive(node.left)
    if (node.type == ops.PAIR):
        checkPairingInputTypes(node)
        return types.GT
    if (node.type == ops.ATTR):
        if (node.attr in varTypes[currentFuncName]):
            return varTypes[currentFuncName][node.attr]
        if (node.attr.find(LIST_INDEX_SYMBOL) != -1):
            (funcNameOfVar, varNameInList) = getVarNameFromListIndices(node)
            if ( (funcNameOfVar == None) or (varNameInList == None) ):
                return types.NO_TYPE
            try:
                retVarType = varTypes[funcNameOfVar][varNameInList]
            except:
                (outsideFunctionName, retVarInfoObj) = getVarNameEntryFromAssignInfo(varNameInList)
                retVarType = varTypes[outsideFunctionName][varNameInList]

            print(node)
            print(retVarType)
            print("\n")
            return retVarType

    return types.NO_TYPE

def getVarTypeInfo(node, varName):
    if (currentFuncName == TYPES_HEADER):
        updateVarTypes(varTypes[currentFuncName], varName, assignInfo[currentFuncName][varName].getType())
        return

    retVarType = getVarTypeInfoRecursive(node.right)
    if (retVarType != types.NO_TYPE):
        updateVarTypes(varTypes[currentFuncName], varName, retVarType)

def updateAssignInfo(node, i):
    global assignInfo, forLoops, varTypes

    if (currentFuncName not in assignInfo):
        assignInfo[currentFuncName] = {}

    if (currentFuncName not in varTypes):
        varTypes[currentFuncName] = {}

    if (currentFuncName not in forLoops):
        forLoops[currentFuncName] = []

    assignInfo_Func = assignInfo[currentFuncName]

    varName = getFullVarName(node.left)
    #print("varName in updateAssignInfo :=", varName)
    if (varName in assignInfo_Func):
        if (assignInfo_Func[varName].hasBeenSet() == True):
            sys.exit("Found multiple assignments of same variable name within same function.")
        assignInfo_Func[varName].setAssignNode(node, currentFuncName)
        assignInfo_Func[varName].setLineNo(i)
    else:
        varInfoObj = VarInfo()
        varInfoObj.setAssignNode(node, currentFuncName)
        varInfoObj.setLineNo(i)
        assignInfo_Func[varName] = varInfoObj

    if (startLineNo_ForLoop != None):
        lenForLoops = len(forLoops[currentFuncName])
        forLoops[currentFuncName][lenForLoops - 1].appendToBinaryNodeList(node)
        forLoops[currentFuncName][lenForLoops - 1].appendToVarInfoNodeList(assignInfo_Func[varName])

    getVarTypeInfo(node, varName)

    global algebraicSetting

    if ( (varName == ALGEBRAIC_SETTING) and (currentFuncName == NONE_FUNC_NAME) ):
        if (algebraicSetting != None):
            sys.exit("Algebraic setting has been set more than once.")
        algSettingVarDepList = assignInfo_Func[varName].getVarDeps()
        if (len(algSettingVarDepList) != 1):
            sys.exit("Wrong number of arguments specified for algebraic setting.")
        if ( (algSettingVarDepList[0] != SYMMETRIC_SETTING) and (algSettingVarDepList[0] != ASYMMETRIC_SETTING) ):
            sys.exit("Incorrect value specified for algebraic setting.")

        algebraicSetting = algSettingVarDepList[0]

def visitMultiLineNodes(node, i):
    if node == None:
        return
    if node.type == ops.EQ:
        #print("statement: ", node)
        updateAssignInfo(BinaryNode.copy(node), i)
        return
    if node.left: visitMultiLineNodes(node.left, i)
    if node.right: visitMultiLineNodes(node.right, i)

def updateForLoopInfo(node, i):    
    varName = 'loop' + str(i)
    print("identified varName: ", varName)    
    # recover assign statements within the for loop
    if (currentFuncName not in assignInfo):
        assignInfo[currentFuncName] = {}

    assignInfo_Func = assignInfo[currentFuncName]
    
    visitMultiLineNodes(node.right, i)
    # record for loop itself for future?
    varInfoObj = VarInfo()
    varInfoObj.setAssignNode(node, currentFuncName)
    varInfoObj.setLineNo(i)
    assignInfo_Func[varName] = varInfoObj
    

def getVarDepList(funcName, varName, retVarDepList, varsVisitedSoFar):
    varsVisitedSoFar.append(varName)
    assignInfo_Var = assignInfo[funcName][varName]
    currentVarDepList = assignInfo_Var.getVarDeps()
    for currentVarDep in currentVarDepList:
        if (currentVarDep not in retVarDepList):
            retVarDepList.append(currentVarDep)
        if ( (currentVarDep in assignInfo[funcName]) and  (currentVarDep not in varsVisitedSoFar) ):
            getVarDepList(funcName, currentVarDep, retVarDepList, varsVisitedSoFar)

def getVarInfList():
    global varInfList

    for funcName in varDepList:
        for varName in varDepList[funcName]:
            currentVarDepList = varDepList[funcName][varName]
            for currentVarDep in currentVarDepList:
                if (varName not in varInfList[funcName][currentVarDep]):
                    varInfList[funcName][currentVarDep].append(varName)

def getVarDepInfLists():
    global varDepList, varInfList

    for funcName in assignInfo:
        varDepList[funcName] = {}
        varInfList[funcName] = {}
        assignInfo_Func = assignInfo[funcName]
        for varName in assignInfo_Func:
            retVarDepList = []
            getVarDepList(funcName, varName, retVarDepList, [])
            varDepList[funcName][varName] = retVarDepList
            for retVarDep in retVarDepList:
                varInfList[funcName][retVarDep] = []

    getVarInfList()

def getVarsThatProtectM():
    global varsThatProtectM

    for funcName in assignInfo:
        varsThatProtectM[funcName] = []
        assignInfo_Func = assignInfo[funcName]
        for varName in assignInfo_Func:
            assignInfo_Var = assignInfo_Func[varName]
            if (assignInfo_Var.getProtectsM() == True and varName not in ASSIGN_KEYWORDS):
                varsThatProtectM[funcName].append(varName)

def updateForLoops(node, lineNo):
    if (startLineNo_ForLoop == None):
        sys.exit("updateForLoops function entered in SDLParser.py when startLineNo_ForLoop is set to None.")

    global forLoops

    retForLoopStruct = ForLoop()
    retForLoopStruct.updateForLoopStruct(node, startLineNo_ForLoop, currentFuncName)

    forLoops[currentFuncName].append(retForLoopStruct)

# NEW SDL PARSER
def parseFile2(filename):
    fd = open(filename, 'r')
    code = fd.readlines(); i = 0
    parser = SDLParser() 
    ast_code = []
    for line in code:
        i += 1
        if len(line.strip()) > 0:
            node = parser.parse(line, i)
            #print("sdl: ", i, node)
            ast_code.append(node)
            #i += 1
            if (node.type == ops.EQ):
                updateAssignInfo(node, i)
            elif (node.type == ops.DO): # handles for loop
                updateForLoopInfo(node, i)
            elif (node.type == ops.FOR):
                updateForLoops(node, i)

# Perform some type checking here?
# rules: find constants, verify, variable definitions
def astParser(astList):
    constants = []
    verify_eq = None
    variables = {}
    
    for i in astList:
        s = str(i.left)
        if s == 'constant':
            constants.append(str(i.right))
        elif s == 'verify':
            verify_eq = i
        else:
            variables[s] = str(i.right)

    return (constants, verify_eq, variables)

class ASTIterator:
    def __init__(self, _node, _type):
        self.cur_node = _node
        self.of_type = _type
    
    def __iter__(self):
        # if we've found a match
        if self.cur_node.type == _type:
            return self.cur_node
        else:
            self.cur_node = self.cur_node.right
    
    def next(self):
        if self.cur_node:
            raise StopIteration
        else:
            self.cur_node = _node.right

# decorator for selecting which operation to call on 
# each node visit...
class dispatch(object):
    def __init__(self, target=None):
#        print("initialized dispatcher...")
        self.target = target
        self.default = 'visit'        
        #self.meths = {}; 
        self.hit = 0
    
    def __call__(self, visitor, *args):
        def wrapped_func(*args):
            try:
                name = str(args[0].type)
                #print("dispatch for => visit_", name.lower())
                func_name = 'visit_' + name.lower()
                if hasattr(visitor, 'cache') and visitor.cache.get(func_name) == None:
                    meth = getattr(visitor, func_name, self.default)
                    if meth == self.default:
                        meth = getattr(visitor, self.default)
                    visitor.cache[func_name] = meth # cache for next call
                    return meth(*args)
                else:
                    # call cached function
                    self.hit += 1
                    # print("hitting cache: ", self.hit) 
                    return visitor.cache[func_name](*args)
            except Exception as e:
                print(e)

        return wrapped_func(*args)

class ASTVisitor(object):
    def __init__(self, visitor):    
        self.visitor = visitor
        if not hasattr(self.visitor, 'visit'):
            raise Exception("No generic visit method defined in AST operation class")
        if not hasattr(self.visitor, 'cache'):
            self.visitor.cache = {} # for caching funcs
        # pointers to other parts of the tree
        # allows for keeping track of where we are in
        # AST.

    @dispatch
    def visit(self, visitor, node, info):
        """Generic visit function or sub nodes"""
        return
        
    def preorder(self, root_node, parent_node=None, sib_node=None, pass_info=None):
        if root_node == None: return None
        # if parent_node == None: parent_node = root_node
        info = { 'parent': parent_node, 'sibling': sib_node }
        if pass_info and type(pass_info) == dict: 
            #print("special info passed: ", pass_info)
            info.update(pass_info) 

        result = self.visit(self.visitor, root_node, info) 

        # allow other information to be passed between visitation of nodes
        if result == None: result = pass_info # if no knew information is added from the last visitation then
        elif type(result) == dict and type(pass_info) == dict: result.update(pass_info) # they passed something else back, so we add to pass_info
        elif type(result) == dict and pass_info == None: pass # no need to update result dict
        else: assert False, "can ONLY return dictionaries from visit methods." # should raise an exception here
        
        self.preorder(root_node.left, root_node, root_node.right, result)
        self.preorder(root_node.right, root_node, root_node.left, result)
    
    # TODO: need to think about how to pass information when we perform the bottom up tree traversal.
    def postorder(self, root_node, parent_node=None, sib_node=None, pass_info=None):
        if root_node == None: return None
        # if parent_node == None: parent_node = root_node
        info = { 'parent': parent_node, 'sibling': sib_node }
        self.postorder(root_node.left, root_node, root_node.right)
        self.postorder(root_node.right, root_node, root_node.left)
        self.visit(self.visitor, root_node, info)
    
    # TODO: think about how to pass info when traversing in order. 
    def inorder(self, root_node, parent_node=None, sib_node=None, pass_info=None):
        if root_node == None: return None
        # if parent_node == None: parent_node = root_node        
        info = { 'parent': parent_node, 'sibling': sib_node }
        self.inorder(root_node.left, root_node, root_node.right)
        self.visit(self.visitor, root_node, info)
        self.inorder(root_node.right, root_node, root_node.left)


def addAsChildNodeToParent(data, target_node):
    if data['parent'].right == data['sibling']:
        data['parent'].left = target_node
    else:
        data['parent'].right = target_node              

        
# for single signer scenario only
class CombineVerifyEq:
    def __init__(self, constants, variables):
        self.consts = constants
        self.vars = variables
    
    def visit(self, node, data):
        pass
    
    def visit_eq_tst(self, node, data):
        # distribute prod to left and right side
        if node.left.type != ops.EQ:
            prodL = self.newProdNode()
            prodL.right = node.left
            node.left = prodL
        
        if node.right.type != ops.EQ:
            prodR = self.newProdNode()
            prodR.right = node.right
            node.right = prodR
                    
    def visit_attr(self, node, data):
        if data['parent'].type in [ops.PROD, ops.EQ]:
            return
        if not self.isConstant(node):
            node.setAttrIndex('z') # add index to each attr that isn't constant
    
    def newProdNode(self):
        p = BatchParser()
        new_node = p.parse("prod{z:=0, N} on x")
        return new_node

    def isConstant(self, node):
        if self.consts:        
            for n in self.consts:
                if n == node.getAttribute(): return True            
            #if n.getAttribute() == node.getAttribute(): return True
        return False

class CVForMultiSigner:
    def __init__(self, var_types, sig_vars, pub_vars, msg_vars, setting):
        self.vars = var_types
        if pub_vars:
            assert type(pub_vars) == list, "public vars needs to be in a list"
            self.pub  = pub_vars # list of variable names
        else:
            self.pub = None
            
        if sig_vars:
            assert type(sig_vars) == list, "signature vars need to be in a list"
            self.sig  = sig_vars # list of variable names
        else:
            self.sig = None
            
        if msg_vars:
            assert type(msg_vars) == list, "message vars need to be in a list"
            self.msg  = msg_vars
        else:
            self.msg = None
        self.setting = setting

        #TODO: process setting to determine whether we qualify for single or multi-signer mode
        self.sigKey = 'z'; self.sigEnd = setting[SIGNATURE]
        self.pubEnd = None
#        if setting[PUBLIC] == SAME and setting[SIGNATURE] == setting[MESSAGE]:
        if setting[ PUBLIC ] and setting[ MESSAGE ]:
            if setting[SIGNATURE] == setting[MESSAGE] and setting[PUBLIC] == SAME:
                self.signer = signer_mode.single
                self.pubKey = self.sigKey
                print("Mode: ", self.signer, "signer")
            elif setting[PUBLIC] == setting[SIGNATURE]:
            # technically multi-signer, but since there is a 
            # one-to-one mapping with sigs and public keys
            # we should just call it single signer. Equation turns out 
            # to be the same
                self.signer = signer_mode.single            
                self.pubKey = self.sigKey
                self.pubEnd = self.sigEnd
                print("Mode: multi signer") 
            elif setting[PUBLIC] != setting[SIGNATURE] and setting[PUBLIC] == SAME:
                self.signer = signer_mode.single
                self.pubKey = self.pubEnd = None
                print("Mode: ", self.signer, "signer")
            elif setting[PUBLIC] != setting[SIGNATURE]:
            # most likely multi-signer mode
                self.signer = signer_mode.multi
                self.pubKey = 'y' # reserved for different amount of signers than signatures
                self.pubEnd = setting[PUBLIC]
                print("Mode: ", self.signer, "signer")
            else:
                print("error?")
        else:
            # if None for either or both (most likely a different setting)
            if setting[SIGNATURE]:
                self.signer = signer_mode.ring
                print("Mode: ", self.signer, "signer")
           
    def visit(self, node, data):
        pass
    
    def visit_eq_tst(self, node, data):
        # distribute prod to left and right side
        if self.signer >= signer_mode.single:
            if Type(node.left) != ops.EQ and str(node.left) != '1':
                prodL = self.newProdNode(self.sigKey, self.sigEnd) # check if sig vars appear in left side?
                prodL.right = node.left
                node.left = prodL
        
            if Type(node.right) != ops.EQ and str(node.right) != '1':
                prodR = self.newProdNode(self.sigKey, self.sigEnd)
                prodR.right = node.right
                node.right = prodR
            
        # check whether the pub vars appear in left subtree
        if self.signer == signer_mode.multi:
            if Type(node.left) != ops.EQ and self.isPubInSubtree(node.left):
                prodL2 = self.newProdNode(self.pubKey, self.pubEnd)
                prodL2.right = node.left
                node.left = prodL2
            elif Type(node.right) != ops.EQ and self.isPubInSubtree(node.right):
                prodR2 = self.newProdNode(self.pubKey, self.pubEnd)
                prodR2.right = node.right
                node.right   = prodR2
        else:
            pass

                    
    def visit_attr(self, node, data):
        if data['parent'].type in [ops.PROD, ops.EQ, ops.FOR, ops.SUM]:
            return
        if self.isSig(node):
            node.setAttrIndex('z') # add index to each attr that isn't constant
        
        # handle public keys
        if self.isPub(node):
            if self.setting[PUBLIC] == SAME:
                pass
            elif self.signer == signer_mode.single:
                node.setAttrIndex('z')
            elif self.signer == signer_mode.multi:
                node.setAttrIndex('y')
                
        if self.isMsg(node) and self.setting[MESSAGE] == self.setting[SIGNATURE]:
            #print("visiting: ", node, self.setting[ MESSAGE ])
            node.setAttrIndex('z')
    
    def newProdNode(self, key=None, end=None):
        p = BatchParser()
        if key and end:
            new_node = p.parse("prod{"+key+":=0,"+end+"} on x")        
        else:
            new_node = p.parse("prod{z:=0, N} on x")
        return new_node

    def isPub(self, node):
        if self.pub:        
            for n in self.pub:
                if n == node.getAttribute(): return True            
            #if n.getAttribute() == node.getAttribute(): return True
        return False

    def isSig(self, node):
        if self.sig:        
            for n in self.sig:
                if n == node.getAttribute(): return True            
            #if n.getAttribute() == node.getAttribute(): return True
        return False

    def isMsg(self, node):
        if self.msg:        
            for n in self.msg:
                if n == node.getAttribute(): return True            
            #if n.getAttribute() == node.getAttribute(): return True
        return False

    def isPubInSubtree(self, tree):
        if tree == None: return None
        elif Type(tree) == ops.ATTR and self.isPub(tree):
            return True
        else:
            result = self.isPubInSubtree(tree.left)
            if result: return result # if True, then end search else continue
            return self.isPubInSubtree(tree.right)
            


# Focuses on simplifying dot products of the form
# prod{} on (x * y)
class SimplifyDotProducts:
    def __init__(self):
        self.rule = "Distribute dot products: "

    def getMulTokens(self, subtree, parent_type, target_type, _list):
        if subtree == None: return None
        elif parent_type == ops.EXP and Type(subtree) == ops.MUL:
            return               
        elif parent_type == ops.MUL:
            if Type(subtree) in target_type: 
                found = False
                for i in _list:
                    if isNodeInSubtree(i, subtree): found = True
                if not found: _list.append(subtree)

        if subtree.left: self.getMulTokens(subtree.left, subtree.type, target_type, _list)
        if subtree.right: self.getMulTokens(subtree.right, subtree.type, target_type, _list)
        return
    
    def visit(self, node, data):
        pass

    # visit all the ON nodes and test whether we can distribute the product to children nodes
    # e.g., prod{} on (x * y) => prod{} on x * prod{} on y    
    def visit_on(self, node, data):
        if Type(data['parent']) == ops.PAIR:
            #self.rule += "False "
            return
        #print("test: right node of prod =>", node.right, ": type =>", node.right.type)
        #print("parent type =>", Type(data['parent']))
#        _type = node.right.type
        if Type(node.right) == ops.MUL:            
            # must distribute prod to both children of mul
            r = []
            mul_node = node.right
            self.getMulTokens(mul_node, ops.NONE, [ops.EXP, ops.HASH, ops.PAIR, ops.ATTR], r)
            #for i in r:
            #    print("node =>", i)
            
            if len(r) == 0:
                pass
            elif len(r) <= 2:
            # in case we're dealing with prod{} on attr1 * attr2 
            # no need to simply further, so we can simply return
                if mul_node.left.type == ops.ATTR and mul_node.right.type == ops.ATTR:
                    return

                node.right = None
                prod_node2 = BinaryNode.copy(node)
            
            # add prod nodes to children of mul_node
                prod_node2.right = mul_node.right
                mul_node.right = prod_node2
            
                node.right = mul_node.left
                mul_node.left = node
                #self.rule += "True "
                # move mul_node one level up to replace the "on" node.
                addAsChildNodeToParent(data, mul_node)
            elif len(r) > 2:
                #print("original node =>", node)
                muls = [BinaryNode(ops.MUL) for i in range(len(r)-1)]
                prod = [BinaryNode.copy(node) for i in r]
                # distribute the products to all nodes in r
                for i in range(len(r)):
                    prod[i].right = r[i]
#                    print("n =>", prod[i])
                # combine prod nodes into mul nodes                     
                for i in range(len(muls)):
                    muls[i].left = prod[i]
                    if i < len(muls)-1:
                        muls[i].right = muls[i+1]
                    else:
                        muls[i].right = prod[i+1]
#                print("final node =>", muls[0])
                addAsChildNodeToParent(data, muls[0])                
                #self.rule += "True "
            else:
                #self.rule += "False "
                return                




def print_results(data):
    line = "-----------------------------------------------------------------------------------------------------------------------------------------\n"
    head = "Keys\t|\t\tZR\t\t|\t\tG1\t\t|\t\tG2\t\t|\t\tGT\t\t|\n"
    msmt = line + head + line
    for k in data.keys():
        if k in ['mul', 'exp', 'hash']:
            msmt += k + "\t|"
            for i in ['ZR', 'G1', 'G2', 'GT']:
                msmt += "\t\t" + "%.2f" % data[k][i] + "\t\t|"
            msmt += "\n" + line
    for k in data.keys():
        if k in ['pair', 'prng']:
            msmt += k + " => " + str(data[k]) + "  \n"
            msmt += line            
    print(msmt)
    return

def calculate_times(opcount, curve, N, debugging=False):
    result = {}
    total_time = 0.0
    for i in opcount.keys():
        if i in ['pair', 'prng']:
            result[i] = opcount[i] * curve[i]
            total_time += result[i]
        else: # probably another dictionary
            result[i] = {}
            for j in opcount[i].keys():
                result[i][j] = opcount[i][j] * curve[i][j]
                total_time += result[i][j]
    if debugging: 
        print("Measurements are recorded in milliseconds.")
        print_results(result)
        print("Total Verification Time =>", total_time)
        print("Per Signature =>", total_time / N, "\n")
    return (result, total_time / N)

def printVarDepORInfLists(listToPrint):
    for funcName in listToPrint:
        print("FUNCTION NAME:  " + funcName)
        print("\n")
        for varName in listToPrint[funcName]:
            print(varName)
            print(listToPrint[funcName][varName])
            print("\n")
        print("----------------------")

def printForLoops():
    for funcName in forLoops:
        print("FUNCTION NAME:  " + funcName)
        print("\n")
        for forLoopObj in forLoops[funcName]:
            print("Starting value:  " + str(forLoopObj.getStartVal()))
            print("Ending value:  " + str(forLoopObj.getEndVal()))
            print("Loop variable name:  " + str(forLoopObj.getLoopVar()))
            print("Starting line number:  " + str(forLoopObj.getStartLineNo()))
            print("Ending line number:  " + str(forLoopObj.getEndLineNo()))
            print("Function name:  " + str(forLoopObj.getFuncName()))
            print("Binary Nodes:")
            for binaryNode in forLoopObj.getBinaryNodeList():
                print("\t" + str(binaryNode))
            print("Note:  we also have a list of the VarInfo objects associated with each line of the for loop.")
            print("\n")

def printVarTypes():
    for funcName in varTypes:
        print("FUNCTION NAME:  " + funcName)
        print("\n")
        for varName in varTypes[funcName]:
            print(str(varName) + " -> " + str(varTypes[funcName][varName]))
        print("\n")

def printFinalOutput():
    print("\n")

    '''
    print("Variable dependency list:\n")
    printVarDepORInfLists(varDepList)
    print("\n")
    print("Variable influence list:\n")
    printVarDepORInfLists(varInfList)
    print("\n")

    print("Variables that protect the message:\n")
    #print(varsThatProtectM)
    print("Ayo:  can you get this information from the two data structures I have shown above?")
    print("If so, please access the message variable using the name M (defined in config.py) rather")
    print("than hard-coding 'M' so we can keep it flexible for the user.")
    print("If not, let me know so I can re-write the getVarsThatProtectM() method to make it what")
    print("you need.\n")
    print("-------------------------")
    print("\n")
    '''

    print("Variable types inferred so far (more to come soon):\n")
    #printVarTypes()
    print("\n")
    print("----------------------------")
    print("\n")

    '''
    print("For loops:\n")
    printForLoops()
    print("\n")
    '''

if __name__ == "__main__":
    #print(sys.argv[1:])
    if sys.argv[1] == '-t':
        debug = levels.all
        statement = sys.argv[2]
        parser = SDLParser()
        final = parser.parse(statement)
        print("Final statement:  '%s'" % final)
        exit(0)
    else:
        parseFile2(sys.argv[1])
        getVarDepInfLists()
        getVarsThatProtectM()
        printFinalOutput()

        # read contents of file
        # 
#    elif sys.argv[1] == '-p':
#        print_results(None)
#        exit(0)
#    #elif sys.argv[1] == '-n':
#    
#    # main for batch input parser    
#    file = sys.argv[1]
#    ast_struct = parseFile(file)
#    const, types = ast_struct[ CONST ], ast_struct[ TYPE ]
#    precompute = ast_struct[ PRECOMP ]
#    algorithm = ast_struct [ TRANSFORM ]
#    verify, N = None, None
#    metadata = {}
#    for n in ast_struct[ OTHER ]:
#        if str(n.left) == 'verify':
#            verify = n
#        elif str(n.left) == 'N':
#            N = int(str(n.right))
#            metadata['N'] = str(n.right)
#        else:
#            metadata[ str(n.left) ] = str(n.right)
#
 